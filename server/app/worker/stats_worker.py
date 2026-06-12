"""
统计聚合 Worker — 每小时预聚合 daily_stats_merchant + daily_stats_category。
避免供应商每次查看对账看板时实时 SQL SUM/COUNT。
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.postgres.session import async_session_factory

logger = logging.getLogger("stats_worker")

POLL_INTERVAL = 3600  # every hour


async def _aggregate_merchant_stats(session: AsyncSession, target_date: str) -> int:
    """聚合指定日期的按 API 支付商统计。"""
    await session.execute(text(
        "DELETE FROM daily_stats_merchant WHERE stat_date=CAST(:dt AS DATE)"
    ).bindparams(dt=target_date))
    r = await session.execute(text("""
        INSERT INTO daily_stats_merchant (supplier_id, api_payer_id, stat_date,
            total_orders, success_orders, total_amount, success_amount)
        SELECT o.supplier_id, o.api_payer_id, CAST(:dt AS DATE),
               COUNT(*),
               COUNT(*) FILTER (WHERE o.status = 'SUCCESS'),
               COALESCE(SUM(o.amount), 0),
               COALESCE(SUM(o.amount) FILTER (WHERE o.status = 'SUCCESS'), 0)
        FROM orders o
        WHERE o.created_at >= CAST(:dt AS DATE)
          AND o.created_at < CAST(:dt AS DATE) + INTERVAL '1 day'
        GROUP BY o.supplier_id, o.api_payer_id
    """).bindparams(dt=target_date))
    count = r.rowcount if r else 0
    logger.info("Aggregated %d merchant stats rows for %s", count, target_date)
    return count


async def _aggregate_category_stats(session: AsyncSession, target_date: str) -> int:
    """聚合指定日期的按品类统计。"""
    await session.execute(text(
        "DELETE FROM daily_stats_category WHERE stat_date=CAST(:dt AS DATE)"
    ).bindparams(dt=target_date))
    r = await session.execute(text("""
        INSERT INTO daily_stats_category (supplier_id, product_id, stat_date,
            total_orders, total_amount)
        SELECT o.supplier_id, o.product_id, CAST(:dt AS DATE),
               COUNT(*),
               COALESCE(SUM(o.amount), 0)
        FROM orders o
        WHERE o.created_at >= CAST(:dt AS DATE)
          AND o.created_at < CAST(:dt AS DATE) + INTERVAL '1 day'
        GROUP BY o.supplier_id, o.product_id
    """).bindparams(dt=target_date))
    count = r.rowcount if r else 0
    logger.info("Aggregated %d category stats rows for %s", count, target_date)
    return count


async def _run_cycle():
    """One cycle: aggregate today and yesterday."""
    today = str(datetime.now(timezone.utc).date())
    yesterday = str(datetime.now(timezone.utc).date().isoformat())

    try:
        async with async_session_factory() as session:
            await _aggregate_merchant_stats(session, today)
            await _aggregate_category_stats(session, today)
            await session.commit()
    except Exception as e:
        logger.error("Stats worker cycle error: %s", e)


async def start_stats_worker():
    """启动统计聚合 Worker（在 app lifespan 中调用）。"""
    logger.info("Stats worker started (poll every %ds)", POLL_INTERVAL)
    # Initial run on startup
    await _run_cycle()
    while True:
        await asyncio.sleep(POLL_INTERVAL)
        await _run_cycle()
