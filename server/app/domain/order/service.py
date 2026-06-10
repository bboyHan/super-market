from __future__ import annotations

from uuid import UUID

from app.domain.order.entity import Order, OrderCreatedEvent, OrderStatus
from app.domain.order.repository import OrderRepository
from app.infrastructure.queue.event_bus import EventBus


class OrderService:
    """Application service for order domain operations."""

    def __init__(self, repo: OrderRepository, event_bus: EventBus) -> None:
        self._repo = repo
        self._event_bus = event_bus

    async def create_order(self, order: Order) -> Order:
        """Create a new order and publish OrderCreatedEvent."""
        await self._repo.save(order)
        event = OrderCreatedEvent(
            order_id=order.id,
            order_no=order.order_no,
            merchant_id=order.merchant_id or UUID(int=0),
        )
        await self._event_bus.publish(event)
        return order

    async def get_order(self, order_id: UUID) -> Order | None:
        """Retrieve an order by ID."""
        return await self._repo.get_by_id(order_id)

    async def get_order_by_no(self, order_no: str) -> Order | None:
        """Retrieve an order by its order number."""
        return await self._repo.get_by_order_no(order_no)

    async def cancel_order(self, order_id: UUID) -> Order | None:
        """Cancel an order if allowed by its current state."""
        order = await self._repo.get_by_id(order_id)
        if not order:
            return None
        order.cancel()
        await self._repo.save(order)
        return order

    async def mark_success(self, order_id: UUID) -> Order | None:
        """Mark an order as successfully delivered."""
        order = await self._repo.get_by_id(order_id)
        if not order:
            return None
        order.mark_success()
        await self._repo.save(order)
        return order
