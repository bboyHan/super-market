from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4


class AgentStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class Agent:
    """Agent (downstream merchant / reseller) entity."""

    def __init__(
        self,
        name: str,
        supplier_id: UUID | None = None,
        balance: float = 0.0,
        status: AgentStatus = AgentStatus.ACTIVE,
        api_key: str = "",
        callback_url: str = "",
        id: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.id = id or uuid4()
        self.name = name
        self.supplier_id = supplier_id
        self.balance = balance
        self.status = status
        self.api_key = api_key
        self.callback_url = callback_url
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or self.created_at

    def __repr__(self) -> str:
        return f"<Agent id={self.id} name={self.name} status={self.status.value}>"


class InventoryItemStatus(str, enum.Enum):
    AVAILABLE = "available"
    USED = "used"
    EXPIRED = "expired"
    REFUNDED = "refunded"


class InventoryItem:
    """A single inventory unit (e.g. a card code / serial) held by an agent."""

    def __init__(
        self,
        agent_id: UUID,
        product_id: UUID,
        content: str = "",
        status: InventoryItemStatus = InventoryItemStatus.AVAILABLE,
        external_ref: str = "",
        id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> None:
        self.id = id or uuid4()
        self.agent_id = agent_id
        self.product_id = product_id
        self.content = content
        self.status = status
        self.external_ref = external_ref
        self.created_at = created_at or datetime.utcnow()

    def mark_used(self) -> None:
        if self.status != InventoryItemStatus.AVAILABLE:
            raise InventoryStateError(
                f"Cannot use item in state {self.status}"
            )
        self.status = InventoryItemStatus.USED

    def mark_expired(self) -> None:
        if self.status == InventoryItemStatus.USED:
            return
        self.status = InventoryItemStatus.EXPIRED

    def __repr__(self) -> str:
        return (
            f"<InventoryItem id={self.id} agent={self.agent_id} "
            f"product={self.product_id} status={self.status.value}>"
        )


class InventoryStateError(Exception):
    """Raised on invalid inventory item state transition."""

    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(message)
