from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.order.entity import Order


class OrderRepository(ABC):
    """Repository interface for Order aggregate."""

    @abstractmethod
    async def save(self, order: Order) -> None:
        """Persist an order (insert or update)."""
        ...

    @abstractmethod
    async def get_by_id(self, order_id: UUID) -> Order | None:
        """Retrieve an order by its primary key."""
        ...

    @abstractmethod
    async def get_by_order_no(self, order_no: str) -> Order | None:
        """Retrieve an order by its unique order number."""
        ...

    @abstractmethod
    async def list_by_merchant(
        self,
        merchant_id: UUID,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Order]:
        """List orders belonging to a merchant with pagination."""
        ...

    @abstractmethod
    async def delete(self, order_id: UUID) -> None:
        """Delete an order by id."""
        ...
