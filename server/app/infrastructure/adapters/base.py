from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class PlatformAdapter(ABC):
    """Base class for third-party platform / supplier adapters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique adapter identifier (e.g. 'supplier_alipay')."""
        ...

    @abstractmethod
    async def submit_order(self, order_id: UUID, product_id: UUID, **kwargs: Any) -> dict[str, Any]:
        """Submit an order to the upstream platform."""
        ...

    @abstractmethod
    async def query_order(self, order_id: UUID) -> dict[str, Any]:
        """Query order status from the upstream platform."""
        ...

    @abstractmethod
    async def check_balance(self) -> float:
        """Check remaining balance on the upstream platform."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check whether the upstream platform is reachable."""
        ...
