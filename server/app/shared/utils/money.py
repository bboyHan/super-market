from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Union

# Type alias for anything that can be converted to Decimal
Number = Union[int, float, str, Decimal]


def to_decimal(value: Number, places: int = 2) -> Decimal:
    """Convert a value to Decimal with given precision (default: 2 decimal places)."""
    return Decimal(str(value)).quantize(Decimal(10) ** -places, rounding=ROUND_HALF_UP)


def format_money(amount: Decimal, currency: str = "CNY") -> str:
    """Format a Decimal amount as a human-readable money string."""
    symbol = {"CNY": "¥", "USD": "$", "EUR": "€"}.get(currency, "")
    return f"{symbol}{amount:.2f}"


def parse_money(value: str) -> Decimal:
    """Parse a money string (e.g. '12.50', '¥12.50') to Decimal."""
    cleaned = value.replace("¥", "").replace("$", "").replace("€", "").replace(",", "").strip()
    return Decimal(cleaned).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def add(a: Number, b: Number) -> Decimal:
    """Safely add two monetary values."""
    return to_decimal(a) + to_decimal(b)


def subtract(a: Number, b: Number) -> Decimal:
    """Safely subtract two monetary values."""
    return to_decimal(a) - to_decimal(b)


def multiply(a: Number, b: Number) -> Decimal:
    """Safely multiply two monetary values."""
    return (to_decimal(a) * to_decimal(b)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
