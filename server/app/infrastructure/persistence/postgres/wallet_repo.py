from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.wallet.entity import Transaction, Wallet
from app.domain.wallet.repository import WalletRepository
from app.infrastructure.persistence.postgres.models import WalletModel, TransactionModel


class PostgresWalletRepository(WalletRepository):
    """PostgreSQL-backed wallet repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, wallet: Wallet) -> None:
        stmt = select(WalletModel).where(WalletModel.id == wallet.id)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.merchant_id = wallet.merchant_id
            existing.balance = wallet.balance
            existing.frozen = wallet.frozen
            existing.currency = wallet.currency
            existing.updated_at = wallet.updated_at
        else:
            model = WalletModel(
                id=wallet.id,
                merchant_id=wallet.merchant_id,
                balance=wallet.balance,
                frozen=wallet.frozen,
                currency=wallet.currency,
                created_at=wallet.created_at,
                updated_at=wallet.updated_at,
            )
            self._session.add(model)

    async def get_by_id(self, wallet_id: UUID) -> Wallet | None:
        stmt = select(WalletModel).where(WalletModel.id == wallet_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._model_to_wallet(model) if model else None

    async def get_by_merchant_id(self, merchant_id: UUID) -> Wallet | None:
        stmt = select(WalletModel).where(WalletModel.merchant_id == merchant_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._model_to_wallet(model) if model else None

    async def save_transaction(self, transaction: Transaction) -> None:
        model = TransactionModel(
            id=transaction.id,
            wallet_id=transaction.wallet_id,
            type=transaction.type.value,
            amount=transaction.amount,
            balance_before=transaction.balance_before,
            balance_after=transaction.balance_after,
            ref_id=transaction.ref_id,
            remark=transaction.remark,
            created_at=transaction.created_at,
        )
        self._session.add(model)

    async def list_transactions(
        self,
        wallet_id: UUID,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Transaction]:
        stmt = (
            select(TransactionModel)
            .where(TransactionModel.wallet_id == wallet_id)
            .offset(offset)
            .limit(limit)
            .order_by(TransactionModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._model_to_tx(m) for m in result.scalars().all()]

    # ── helpers ──────────────────────────────────────────

    def _model_to_wallet(self, model: object) -> Wallet:
        return Wallet(
            id=model.id,  # type: ignore[attr-defined]
            merchant_id=model.merchant_id,  # type: ignore[attr-defined]
            balance=model.balance,  # type: ignore[attr-defined]
            frozen=model.frozen,  # type: ignore[attr-defined]
            currency=model.currency,  # type: ignore[attr-defined]
            created_at=model.created_at,  # type: ignore[attr-defined]
            updated_at=model.updated_at,  # type: ignore[attr-defined]
        )

    def _model_to_tx(self, model: object) -> Transaction:
        from app.domain.wallet.entity import TransactionType

        return Transaction(
            id=model.id,  # type: ignore[attr-defined]
            wallet_id=model.wallet_id,  # type: ignore[attr-defined]
            type=TransactionType(model.type),  # type: ignore[attr-defined]
            amount=model.amount,  # type: ignore[attr-defined]
            balance_before=model.balance_before,  # type: ignore[attr-defined]
            balance_after=model.balance_after,  # type: ignore[attr-defined]
            ref_id=model.ref_id,  # type: ignore[attr-defined]
            remark=model.remark,  # type: ignore[attr-defined]
            created_at=model.created_at,  # type: ignore[attr-defined]
        )
