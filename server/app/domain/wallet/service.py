from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.domain.wallet.entity import (
    InsufficientBalanceError,
    Transaction,
    TransactionType,
    Wallet,
)
from app.domain.wallet.repository import WalletRepository


class WalletService:
    """Application service for wallet domain operations."""

    def __init__(self, repo: WalletRepository) -> None:
        self._repo = repo

    async def get_wallet(self, merchant_id: UUID) -> Wallet | None:
        """Get or create a wallet for a merchant."""
        wallet = await self._repo.get_by_merchant_id(merchant_id)
        if not wallet:
            wallet = Wallet(merchant_id=merchant_id)
            await self._repo.save(wallet)
        return wallet

    async def credit(self, merchant_id: UUID, amount: Decimal, ref_id: str = "") -> Wallet | None:
        """Add funds to a merchant's wallet."""
        wallet = await self.get_wallet(merchant_id)
        if not wallet:
            return None
        balance_before = wallet.balance
        wallet.credit(amount)
        await self._repo.save(wallet)
        tx = Transaction(
            wallet_id=wallet.id,
            type=TransactionType.CREDIT,
            amount=amount,
            balance_before=balance_before,
            balance_after=wallet.balance,
            ref_id=ref_id or "",
        )
        await self._repo.save_transaction(tx)
        return wallet

    async def debit(self, merchant_id: UUID, amount: Decimal, ref_id: str = "") -> Wallet | None:
        """Deduct funds from a merchant's wallet."""
        wallet = await self.get_wallet(merchant_id)
        if not wallet:
            return None
        balance_before = wallet.balance
        try:
            wallet.debit(amount)
        except InsufficientBalanceError:
            raise
        await self._repo.save(wallet)
        tx = Transaction(
            wallet_id=wallet.id,
            type=TransactionType.DEBIT,
            amount=amount,
            balance_before=balance_before,
            balance_after=wallet.balance,
            ref_id=ref_id or "",
        )
        await self._repo.save_transaction(tx)
        return wallet
