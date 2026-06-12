"""
Redis 实时计数 — 今日订单数、交易额等高频统计。
避免每次查询都 COUNT/SUM 数据库。
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from redis.asyncio import Redis

# Redis key prefix
_PREFIX = "dc:"  # daily counter


def _today_key(supplier_id: int, metric: str) -> str:
    """生成今日计数 key。每天自动过期。"""
    d = date.today().isoformat()
    return f"{_prefix}{d}:{metric}"

    # Redis pipeline for atomic increment


class DailyCounter:
    """每日计数器 — 基于 Redis 的实时计数。"""

    def __init__(self, redis: Redis):
        self._redis = redis

    async def incr_order(self, supplier_id: int, amount: int) -> None:
        """订单创建时：订单数 +1，交易额 +amount。"""
        pipe = self._redis.pipeline()
        pipe.incr(_today_key(supplier_id, "orders"))
        pipe.incrby(_today_key(supplier_id, "amount"), amount)
        # Set TTL at midnight
        pipe.expire(_today_key(supplier_id, "orders"), 86400)
        pipe.expire(_today_key(supplier_id, "amount"), 86400)
        await pipe.execute()

    async def get_today(self, supplier_id: int) -> dict:
        """获取今日累计数据。"""
        orders, amount = await self._redis.mget(
            _today_key(supplier_id, "orders"),
            _today_key(supplier_id, "amount"),
        )
        return {
            "today_orders": int(orders) if orders else 0,
            "today_amount": int(amount) if amount else 0,
        }
