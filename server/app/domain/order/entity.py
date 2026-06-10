from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.shared.utils.id_generator import id_generator


class OrderStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    PENDING = "pending"
    DELIVERING = "delivering"
    SUCCESS = "success"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"


class Order:
    """Order aggregate root."""

    def __init__(
        self,
        order_no: str | None = None,
        merchant_id: UUID | None = None,
        product_id: UUID | None = None,
        amount: Decimal | None = None,
        quantity: int = 1,
        status: OrderStatus = OrderStatus.SUBMITTED,
        callback_url: str | None = None,
        id: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.id = id or uuid4()
        self.order_no = order_no or str(id_generator.next_id())
        self.merchant_id = merchant_id
        self.product_id = product_id
        self.amount = amount
        self.quantity = quantity
        self.status = status
        self.callback_url = callback_url
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or self.created_at
        self._events: list[DomainEvent] = []

    # ── domain events ────────────────────────────────────
    @property
    def events(self) -> list[DomainEvent]:
        return list(self._events)

    def _add_event(self, event: DomainEvent) -> None:
        self._events.append(event)

    def clear_events(self) -> None:
        self._events.clear()

    # ── domain behaviour ─────────────────────────────────
    def mark_pending(self) -> None:
        self.status = OrderStatus.PENDING
        self.updated_at = datetime.utcnow()

    def mark_delivering(self) -> None:
        if self.status not in (OrderStatus.PENDING, OrderStatus.SUBMITTED):
            raise OrderStateError(f"Cannot deliver order in state {self.status}")
        self.status = OrderStatus.DELIVERING
        self.updated_at = datetime.utcnow()

    def mark_success(self) -> None:
        if self.status != OrderStatus.DELIVERING:
            raise OrderStateError(f"Cannot complete order in state {self.status}")
        self.status = OrderStatus.SUCCESS
        self.updated_at = datetime.utcnow()
        self._add_event(OrderPaidEvent(order_id=self.id, order_no=self.order_no))

    def cancel(self, reason: str = "") -> None:
        if self.status in (OrderStatus.SUCCESS, OrderStatus.FAILED):
            raise OrderStateError(f"Cannot cancel order in state {self.status}")
        self.status = OrderStatus.CANCELLED
        self.updated_at = datetime.utcnow()

    def expire(self) -> None:
        if self.status not in (OrderStatus.SUBMITTED, OrderStatus.PENDING):
            return
        self.status = OrderStatus.EXPIRED
        self.updated_at = datetime.utcnow()

    # ── snapshot / equality ──────────────────────────────
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Order):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def __repr__(self) -> str:
        return f"<Order id={self.id} order_no={self.order_no} status={self.status.value}>"


# ── Domain event base ───────────────────────────────────────────────

class DomainEvent:
    """Base class for all domain events."""

    def __init__(self) -> None:
        self.event_id: UUID = uuid4()
        self.occurred_at: datetime = datetime.utcnow()


class OrderCreatedEvent(DomainEvent):
    def __init__(self, order_id: UUID, order_no: str, merchant_id: UUID) -> None:
        super().__init__()
        self.order_id = order_id
        self.order_no = order_no
        self.merchant_id = merchant_id


class OrderPaidEvent(DomainEvent):
    def __init__(self, order_id: UUID, order_no: str) -> None:
        super().__init__()
        self.order_id = order_id
        self.order_no = order_no


# ── Exceptions ──────────────────────────────────────────────────────

class OrderStateError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(message)
