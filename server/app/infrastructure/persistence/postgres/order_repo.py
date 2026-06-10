from __future__ import annotations

from uuid import UUID

from loguru import logger
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.order.entity import Order
from app.domain.order.repository import OrderRepository


class PostgresOrderRepository(OrderRepository):
    """PostgreSQL-backed order repository using raw SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, order: Order) -> None:
        """Upsert an order into the database."""
        from app.infrastructure.persistence.postgres.models import OrderModel

        stmt = select(OrderModel).where(OrderModel.id == order.id)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update
            existing.order_no = order.order_no
            existing.merchant_id = order.merchant_id
            existing.product_id = order.product_id
            existing.amount = order.amount
            existing.quantity = order.quantity
            existing.status = order.status.value
            existing.callback_url = order.callback_url
            existing.updated_at = order.updated_at
        else:
            # Insert
            model = OrderModel(
                id=order.id,
                order_no=order.order_no,
                merchant_id=order.merchant_id,
                product_id=order.product_id,
                amount=order.amount,
                quantity=order.quantity,
                status=order.status.value,
                callback_url=order.callback_url,
                created_at=order.created_at,
                updated_at=order.updated_at,
            )
            self._session.add(model)

        logger.debug("Order saved | id={} order_no={}", order.id, order.order_no)

    async def get_by_id(self, order_id: UUID) -> Order | None:
        from app.infrastructure.persistence.postgres.models import OrderModel

        stmt = select(OrderModel).where(OrderModel.id == order_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._model_to_entity(model) if model else None

    async def get_by_order_no(self, order_no: str) -> Order | None:
        from app.infrastructure.persistence.postgres.models import OrderModel

        stmt = select(OrderModel).where(OrderModel.order_no == order_no)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._model_to_entity(model) if model else None

    async def list_by_merchant(
        self,
        merchant_id: UUID,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Order]:
        from app.infrastructure.persistence.postgres.models import OrderModel

        stmt = (
            select(OrderModel)
            .where(OrderModel.merchant_id == merchant_id)
            .offset(offset)
            .limit(limit)
            .order_by(OrderModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._model_to_entity(m) for m in models]

    async def delete(self, order_id: UUID) -> None:
        from app.infrastructure.persistence.postgres.models import OrderModel

        stmt = delete(OrderModel).where(OrderModel.id == order_id)
        await self._session.execute(stmt)
        logger.debug("Order deleted | id={}", order_id)

    # ── helpers ──────────────────────────────────────────

    def _model_to_entity(self, model: object) -> Order:
        from app.domain.order.entity import OrderStatus

        return Order(
            id=model.id,  # type: ignore[attr-defined]
            order_no=model.order_no,  # type: ignore[attr-defined]
            merchant_id=model.merchant_id,  # type: ignore[attr-defined]
            product_id=model.product_id,  # type: ignore[attr-defined]
            amount=model.amount,  # type: ignore[attr-defined]
            quantity=model.quantity,  # type: ignore[attr-defined]
            status=OrderStatus(model.status),  # type: ignore[attr-defined]
            callback_url=model.callback_url,  # type: ignore[attr-defined]
            created_at=model.created_at,  # type: ignore[attr-defined]
            updated_at=model.updated_at,  # type: ignore[attr-defined]
        )
