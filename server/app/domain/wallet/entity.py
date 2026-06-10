from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4


class TransactionType(str, enum.Enum):
    CREDIT = "credit"
    DEBIT = "debit"
    FREEZE = "freeze"
    UNFREEZE = "unfreeze"


class Wallet:
    """Wallet aggregate."""

    def __init__(
        self,
        merchant_id: UUID,
        balance: Decimal = Decimal("0.00"),
        frozen: Decimal = Decimal("0.00"),
        currency: str = "CNY",
        id: UUID | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.id = id or uuid4()
        self.merchant_id = merchant_id
        self.balance = balance
        self.frozen = frozen
        self.currency = currency
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or self.created_at

    def credit(self, amount: Decimal) -> None:
        """Add funds to the wallet."""
        if amount <= Decimal("0"):
            raise ValueError("Credit amount must be positive")
        self.balance += amount
        self.updated_at = datetime.utcnow()

    def debit(self, amount: Decimal) -> None:
        """Deduct funds from the available balance."""
        if amount <= Decimal("0"):
            raise ValueError("Debit amount must be positive")
        available = self.balance - self.frozen
        if amount > available:
            raise InsufficientBalanceError(
                f"Available balance {available} is less than debit {amount}"
            )
        self.balance -= amount
        self.updated_at = datetime.utcnow()

    def freeze(self, amount: Decimal) -> None:
        """Move funds from available to frozen."""
        if amount <= Decimal("0"):
            raise ValueError("Freeze amount must be positive")
        available = self.balance - self.frozen
        if amount > available:
            raise InsufficientBalanceError(
                f"Available balance {available} is less than freeze {amount}"
            )
        self.frozen += amount
        self.updated_at = datetime.utcnow()

    def unfreeze(self, amount: Decimal) -> None:
        """Release frozen funds back to available."""
        if amount <= Decimal("0"):
            raise ValueError("Unfreeze amount must be positive")
        if amount > self.frozen:
            raise ValueError(
                f"Frozen amount {self.frozen} is less than unfreeze {amount}"
            )
        self.frozen -= amount
        self.updated_at = datetime.utcnow()

    def __repr__(self) -> str:
        return (
            f"<Wallet id={self.id} merchant={self.merchant_id} "
            f"balance={self.balance} frozen={self.frozen}>"
        )


class Transaction:
    """Wallet transaction record."""

    def __init__(
        self,
        wallet_id: UUID,
        type: TransactionType,
        amount: Decimal,
        balance_before: Decimal,
        balance_after: Decimal,
        ref_id: str | None = None,
        remark: str | None = None,
        id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> None:
        self.id = id or uuid4()
        self.wallet_id = wallet_id
        self.type = type
        self.amount = amount
        self.balance_before = balance_before
        self.balance_after = balance_after
        self.ref_id = ref_id
        self.remark = remark
        self.created_at = created_at or datetime.utcnow()

    def __repr__(self) -> str:
        return (
            f"<Transaction id={self.id} type={self.type.value} "
            f"amount={self.amount} wallet={self.wallet_id}>"
        )


class InsufficientBalanceError(Exception):
    """Raised when a wallet has insufficient available balance."""

    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(message)
