from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from arq import ArqRedis
from redis.asyncio import Redis

from app.config import settings
from app.domain.order.repository import OrderRepository
from app.domain.routing.strategy import RoundRobinStrategy, RoutingStrategy
from app.domain.wallet.repository import WalletRepository
from app.infrastructure.adapters.registry import AdapterRegistry
from app.infrastructure.cache.redis_cache import RedisCache
from app.infrastructure.persistence.postgres.order_repo import PostgresOrderRepository
from app.infrastructure.persistence.postgres.session import get_db_session as _get_db_session
from app.infrastructure.queue.event_bus import EventBus


# ── Database session ────────────────────────────────────────────────

async def get_db_session() -> AsyncGenerator[Any, None]:
    """Yield an async SQLAlchemy session."""
    async for session in _get_db_session():
        yield session


# ── Redis ───────────────────────────────────────────────────────────

async def get_redis() -> Redis:
    """Return a shared Redis client."""
    return await Redis.from_url(
        str(settings.REDIS_DSN),
        encoding="utf-8",
        decode_responses=True,
    )


# ── Cache ───────────────────────────────────────────────────────────

async def get_cache(redis: Redis | None = None) -> RedisCache:
    if redis is None:
        redis = await get_redis()
    return RedisCache(redis)


# ── Event bus ───────────────────────────────────────────────────────

async def get_event_bus(redis: Redis | None = None) -> EventBus:
    if redis is None:
        redis = await get_redis()
    return EventBus(redis)


# ── Arq queue ───────────────────────────────────────────────────────

async def get_arq_redis() -> ArqRedis:
    return await ArqRedis.from_pool(
        await Redis.from_url(str(settings.ARQ_REDIS_DSN)),
    )


# ── Repositories ────────────────────────────────────────────────────

async def get_order_repo(
    session: Any | None = None,
) -> OrderRepository:
    if session is None:
        gen = get_db_session()
        session = await anext(gen)  # type: ignore[arg-type]
    return PostgresOrderRepository(session)


async def get_wallet_repo(
    session: Any | None = None,
) -> WalletRepository:
    from app.infrastructure.persistence.postgres.wallet_repo import PostgresWalletRepository

    if session is None:
        gen = get_db_session()
        session = await anext(gen)  # type: ignore[arg-type]
    return PostgresWalletRepository(session)


# ── Domain services ─────────────────────────────────────────────────

async def get_order_service() -> Any:
    from app.domain.order.service import OrderService

    repo = await get_order_repo()
    event_bus = await get_event_bus()
    return OrderService(repo, event_bus)


async def get_wallet_service() -> Any:
    from app.domain.wallet.service import WalletService

    repo = await get_wallet_repo()
    return WalletService(repo)


# ── Routing ─────────────────────────────────────────────────────────

async def get_routing_strategy() -> RoutingStrategy:
    return RoundRobinStrategy()


async def get_routing_engine() -> Any:
    from app.domain.routing.engine import RoutingEngine

    strategy = await get_routing_strategy()
    registry = await get_adapter_registry()
    return RoutingEngine(strategy=strategy, adapter_registry=registry)


# ── Adapters ────────────────────────────────────────────────────────

async def get_adapter_registry() -> AdapterRegistry:
    return AdapterRegistry()
