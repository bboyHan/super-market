"""
订单后台 Worker — 超时自动取消 + Redis 实时计数
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.postgres.session import async_session_factory

logger = logging.getLogger("order_worker")

POLL_INTERVAL = 60  # seconds
ORDER_TIMEOUT_MINUTES = 30


async def _auto_cancel_expired(session: AsyncSession) -> int:
    """自动取消超时未确认的 PENDING 订单并解冻代理商积分。
    返回处理的订单数。
    """
    # 1. Find expired PENDING orders
    rows = await session.execute(
        text("""
            SELECT id, order_no, agent_id, amount
            FROM orders
            WHERE status = 'PENDING'
              AND created_at < NOW() - CAST(:interval AS INTERVAL)
            FOR UPDATE SKIP LOCKED
            LIMIT 50
        """).bindparams(interval=f"{ORDER_TIMEOUT_MINUTES} minutes"))
    expired = rows.all()

    if not expired:
        return 0

    for order_id, order_no, agent_id, amount in expired:
        # 2. Mark order as EXPIRED
        await session.execute(
            text("UPDATE orders SET status='EXPIRED', updated_at=NOW() WHERE id=:id")
            .bindparams(id=order_id))

        # 3. Unfreeze agent wallet points if agent exists
        if agent_id and amount:
            wal = await session.execute(
                text("SELECT id, frozen FROM wallets WHERE owner_type='AGENT' AND owner_id=:aid FOR UPDATE")
                .bindparams(aid=agent_id))
            w = wal.first()
            if w and w[1] >= amount:
                await session.execute(
                    text("UPDATE wallets SET frozen=frozen-:amt, balance=balance+:amt, "
                         "version=version+1, updated_at=NOW() WHERE id=:wid")
                    .bindparams(amt=amount, wid=w[0]))
                await session.execute(
                    text("UPDATE agents SET frozen=frozen-:amt WHERE id=:aid")
                    .bindparams(amt=amount, aid=agent_id))
                await session.execute(
                    text("UPDATE point_freeze_records SET status='UNFROZEN' "
                         "WHERE order_no=:on AND status='FROZEN'")
                    .bindparams(on=order_no))

    await session.commit()
    logger.info("Auto-cancelled %d expired orders", len(expired))
    return len(expired)


async def _run_cycle():
    """One worker cycle: auto-cancel + flush counters."""
    try:
        async with async_session_factory() as session:
            await _auto_cancel_expired(session)
    except Exception as e:
        logger.error("Order worker cycle error: %s", e)


async def start_order_worker():
    """启动订单后台 Worker（在 app lifespan 中调用）。"""
    logger.info("Order worker started (poll every %ds, timeout=%dmin)",
                POLL_INTERVAL, ORDER_TIMEOUT_MINUTES)
    while True:
        await _run_cycle()
        await asyncio.sleep(POLL_INTERVAL)
