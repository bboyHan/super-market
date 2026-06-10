from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.wallet.entity import Wallet, Transaction


class WalletRepository(ABC):
    """Repository interface for Wallet aggregate."""

    @abstractmethod
    async def save(self, wallet: Wallet) -> None:
        ...

    @abstractmethod
    async def get_by_id(self, wallet_id: UUID) -> Wallet | None:
        ...

    @abstractmethod
    async def get_by_merchant_id(self, merchant_id: UUID) -> Wallet | None:
        ...

    @abstractmethod
    async def save_transaction(self, transaction: Transaction) -> None:
        ...

    @abstractmethod
    async def list_transactions(
        self,
        wallet_id: UUID,
        offset: int = 0,
        limit: int = 20,
    ) -> list[Transaction]:
        ...
