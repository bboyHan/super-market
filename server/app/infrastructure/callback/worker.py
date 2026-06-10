"""
Callback retry worker.
Retry schedule: 30s → 5min → 30min → 2h → 6h → 24h (6 retries, then give up)

Called by:
  - Order confirm (PENDING → DELIVERING)
  - Order deliver  (DELIVERING → SUCCESS)
  - Background periodic task (every ~15s)
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("callback")

# Retry schedule in seconds after each attempt
RETRY_SCHEDULE = [30, 300, 1800, 7200, 21600, 86400]  # 30s, 5m, 30m, 2h, 6h, 24h
MAX_RETRIES = len(RETRY_SCHEDULE)
POLL_INTERVAL = 15  # background worker polls every 15 seconds


def _next_retry_delay(attempt: int) -> int | None:
    """Return delay in seconds for retry attempt N (0-indexed).
    Returns None if max retries exceeded."""
    if attempt >= MAX_RETRIES:
        return None
    return RETRY_SCHEDULE[attempt]


# ── Callback payload builder ──────────────────────────────────

def _build_payload(order: tuple) -> dict:
    """Build callback JSON payload from an orders row."""
    return {
        "platform_order_id": order[0],   # order_no
        "client_order_id": order[1],     # client_order_id
        "status": order[2],              # status
    }


# ── Single callback attempt ───────────────────────────────────

async def _attempt_callback(order: tuple, session: AsyncSession) -> bool:
    """Attempt one callback. Returns True if successful (HTTP 200)."""
    order_no = order[0]
    callback_url = order[3]
    payload = _build_payload(order)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(callback_url, json=payload)
            if resp.status_code == 200:
                return True
            logger.warning("Callback %s → %s (status=%d)", order_no, callback_url, resp.status_code)
            return False
    except Exception as e:
        logger.warning("Callback %s failed: %s", order_no, e)
        return False


# ── Enqueue callback (called by order lifecycle endpoints) ────

async def enqueue_callback(order_no: str, session: AsyncSession, *, delay: int = 0):
    """Mark an order for callback. Sets next_retry_at to now + delay."""
    next_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
    await session.execute(
        text("UPDATE orders SET callback_status='PENDING', next_retry_at=:nra WHERE order_no=:on")
        .bindparams(nra=next_at, on=order_no))
    logger.info("Enqueued callback for %s (at %s)", order_no, next_at.isoformat())


# ── Process one callback (called by both enqueue and background worker) ────

async def process_one(order_no: str, session: AsyncSession) -> bool:
    """Attempt callback for a single order. Returns True if successful."""
    row = await session.execute(
        text("SELECT order_no, client_order_id, status, callback_url, callback_cnt "
             "FROM orders WHERE order_no=:on FOR UPDATE")
        .bindparams(on=order_no))
    o = row.first()
    if not o or not o[3]:  # no callback_url
        return False

    ok = await _attempt_callback(o, session)
    now = datetime.now(timezone.utc)

    if ok:
        await session.execute(
            text("UPDATE orders SET callback_status='SUCCESS', callback_cnt=callback_cnt+1, "
                 "callback_at=:ca, next_retry_at=NULL WHERE order_no=:on")
            .bindparams(ca=now, on=order_no))
        logger.info("Callback SUCCESS for %s", order_no)
    else:
        attempt = o[4] + 1  # current attempt count
        delay = _next_retry_delay(attempt)
        if delay is not None:
            nra = now + timedelta(seconds=delay)
            await session.execute(
                text("UPDATE orders SET callback_cnt=callback_cnt+1, callback_at=:ca, "
                     "next_retry_at=:nra WHERE order_no=:on")
                .bindparams(ca=now, nra=nra, on=order_no))
            logger.info("Callback FAIL for %s (attempt %d/%d, retry at %s)",
                        order_no, attempt, MAX_RETRIES, nra.isoformat())
        else:
            await session.execute(
                text("UPDATE orders SET callback_status='FAILED', callback_cnt=callback_cnt+1, "
                     "callback_at=:ca, next_retry_at=NULL WHERE order_no=:on")
                .bindparams(ca=now, on=order_no))
            logger.warning("Callback FAILED permanently for %s (exhausted %d retries)",
                           order_no, MAX_RETRIES)

    await session.commit()
    return ok


# ── Background worker: poll for pending callbacks ─────────────

async def _poll_pending(session_factory) -> int:
    """Poll for pending callbacks and process them. Returns number processed."""
    async with session_factory() as session:
        now = datetime.now(timezone.utc)
        rows = await session.execute(
            text("SELECT order_no FROM orders "
                 "WHERE callback_url != '' AND callback_status != 'SUCCESS' "
                 "AND (next_retry_at IS NULL OR next_retry_at <= :now) "
                 "ORDER BY next_retry_at ASC NULLS FIRST LIMIT 10")
            .bindparams(now=now))
        pending = [(r[0],) for r in rows]

        processed = 0
        for (order_no,) in pending:
            try:
                await process_one(order_no, session)
                processed += 1
            except Exception as e:
                logger.error("Error processing callback for %s: %s", order_no, e)
                await session.rollback()

        if processed:
            logger.info("Callback worker processed %d/%d pending callbacks", processed, len(pending))
        return processed


def start_worker(session_factory):
    """Start the background callback worker. Returns the asyncio task."""
    async def _loop():
        logger.info("Callback worker started (poll interval=%ds)", POLL_INTERVAL)
        while True:
            try:
                await _poll_pending(session_factory)
            except Exception as e:
                logger.error("Callback worker error: %s", e)
            await asyncio.sleep(POLL_INTERVAL)

    task = asyncio.create_task(_loop())
    return task
