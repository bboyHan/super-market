from __future__ import annotations

import json
from typing import Any

from loguru import logger
from redis.asyncio import Redis

from app.domain.order.entity import DomainEvent, OrderCreatedEvent, OrderPaidEvent


class EventBus:
    """Simple event bus backed by Redis Streams."""

    STREAM_KEY = "domain_events"

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def publish(self, event: DomainEvent) -> str:
        """Publish a domain event to the Redis stream. Returns the message ID."""
        payload = self._serialize(event)
        msg_id = await self._redis.xadd(self.STREAM_KEY, payload)
        logger.debug("Event published | id={} type={}", msg_id, type(event).__name__)
        return msg_id

    async def subscribe(
        self,
        group: str = "default-group",
        consumer: str = "default-consumer",
        block_ms: int = 5000,
        count: int = 10,
    ) -> list[dict[str, Any]]:
        """Read pending messages from the stream as a consumer group member."""
        try:
            await self._redis.xgroup_create(self.STREAM_KEY, group, id="0", mkstream=True)
        except Exception:
            # Group already exists — ignore
            pass

        raw = await self._redis.xreadgroup(group, consumer, {self.STREAM_KEY: ">"}, count=count, block=block_ms)
        messages: list[dict[str, Any]] = []
        if raw:
            for stream_name, entries in raw:
                for msg_id, fields in entries:
                    messages.append({"id": msg_id, "fields": fields})
        return messages

    async def ack(self, group: str, msg_id: str) -> None:
        """Acknowledge a processed message."""
        await self._redis.xack(self.STREAM_KEY, group, msg_id)

    async def pending_count(self, group: str) -> int:
        """Get the number of pending (unacked) messages for a group."""
        info = await self._redis.xpending(self.STREAM_KEY, group)
        return info.get("pending", 0) if isinstance(info, dict) else 0

    # ── serialization ────────────────────────────────────

    def _serialize(self, event: DomainEvent) -> dict[str, str]:
        base: dict[str, Any] = {
            "event_type": type(event).__name__,
            "event_id": str(event.event_id),
            "occurred_at": event.occurred_at.isoformat(),
        }
        if isinstance(event, OrderCreatedEvent):
            base["order_id"] = str(event.order_id)
            base["order_no"] = event.order_no
            base["merchant_id"] = str(event.merchant_id)
        elif isinstance(event, OrderPaidEvent):
            base["order_id"] = str(event.order_id)
            base["order_no"] = event.order_no
        return {k: str(v) for k, v in base.items()}
