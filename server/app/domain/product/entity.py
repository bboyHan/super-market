from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4


class ProductStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISCONTINUED = "discontinued"


class Product:
    """Product / SKU entity."""

    def __init__(
        self,
        name: str,
        category: str = "",
        face_value: Decimal = Decimal("0.00"),
        cost_price: Decimal = Decimal("0.00"),
        status: ProductStatus = ProductStatus.ACTIVE,
        description: str = "",
        id: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.id = id or uuid4()
        self.name = name
        self.category = category
        self.face_value = face_value
        self.cost_price = cost_price
        self.status = status
        self.description = description
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or self.created_at

    def __repr__(self) -> str:
        return f"<Product id={self.id} name={self.name} status={self.status.value}>"


class SupplierProductAuthorization:
    """Authorization linking a supplier to a product they can fulfill."""

    def __init__(
        self,
        supplier_id: UUID,
        product_id: UUID,
        wholesale_price: Decimal = Decimal("0.00"),
        is_active: bool = True,
        priority: int = 0,
        id: UUID | None = None,
    ) -> None:
        self.id = id or uuid4()
        self.supplier_id = supplier_id
        self.product_id = product_id
        self.wholesale_price = wholesale_price
        self.is_active = is_active
        self.priority = priority

    def __repr__(self) -> str:
        return (
            f"<SupplierProductAuth supplier={self.supplier_id} "
            f"product={self.product_id} price={self.wholesale_price}>"
        )


class AgentAuthorization:
    """Authorization for an agent to sell a product at a given price."""

    def __init__(
        self,
        agent_id: UUID,
        product_id: UUID,
        sale_price: Decimal = Decimal("0.00"),
        is_active: bool = True,
        id: UUID | None = None,
    ) -> None:
        self.id = id or uuid4()
        self.agent_id = agent_id
        self.product_id = product_id
        self.sale_price = sale_price
        self.is_active = is_active

    def __repr__(self) -> str:
        return (
            f"<AgentAuth agent={self.agent_id} "
            f"product={self.product_id} price={self.sale_price}>"
        )
