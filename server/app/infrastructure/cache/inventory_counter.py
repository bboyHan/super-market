"""
Redis 库存预扣 — 下单时原子 DECR，避免 DB 行锁竞争。
库存不足时快速拒绝，DB 异步落盘。
"""
from __future__ import annotations

from redis.asyncio import Redis

_INV_PREFIX = "inv:"  # inv:{product_id}


class InventoryCounter:
    """基于 Redis 的实时库存计数器。"""

    def __init__(self, redis: Redis):
        self._redis = redis

    async def init_stock(self, product_id: int, total: int) -> None:
        """初始化 Redis 库存（启动时从 DB 加载）。"""
        await self._redis.set(f"{_INV_PREFIX}{product_id}", total)

    async def try_deduct(self, product_id: int, quantity: int = 1) -> bool:
        """原子扣减库存。返回 True 表示扣减成功，False 表示库存不足。"""
        remaining = await self._redis.decrby(f"{_INV_PREFIX}{product_id}", quantity)
        if remaining < 0:
            # Rollback: restore the deducted amount
            await self._redis.incrby(f"{_INV_PREFIX}{product_id}", quantity)
            return False
        return True

    async def get_stock(self, product_id: int) -> int:
        """查询实时库存。"""
        val = await self._redis.get(f"{_INV_PREFIX}{product_id}")
        return int(val) if val else 0

    async def add_stock(self, product_id: int, quantity: int) -> None:
        """增加库存（代理商上传时调用）。"""
        await self._redis.incrby(f"{_INV_PREFIX}{product_id}", quantity)
