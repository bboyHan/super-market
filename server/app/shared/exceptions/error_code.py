from __future__ import annotations

import enum
from typing import Any


class ErrorCode(str, enum.Enum):
    """Unified application error codes."""

    # ── General ──────────────────────────────────────────
    SUCCESS = "00000"
    INTERNAL_ERROR = "10001"
    BAD_REQUEST = "10002"
    NOT_FOUND = "10003"
    UNAUTHORIZED = "10004"
    FORBIDDEN = "10005"
    RATE_LIMITED = "10006"
    METHOD_NOT_ALLOWED = "10007"
    CONFLICT = "10008"
    UNPROCESSABLE_ENTITY = "10009"

    # ── Auth ─────────────────────────────────────────────
    INVALID_SIGNATURE = "20001"
    TOKEN_EXPIRED = "20002"
    TOKEN_INVALID = "20003"
    INVALID_API_KEY = "20004"
    SIGNATURE_EXPIRED = "20005"

    # ── Order ────────────────────────────────────────────
    ORDER_NOT_FOUND = "30001"
    ORDER_STATE_ERROR = "30002"
    ORDER_EXPIRED = "30003"
    ORDER_DUPLICATE = "30004"
    INVALID_ORDER_AMOUNT = "30005"

    # ── Wallet ───────────────────────────────────────────
    INSUFFICIENT_BALANCE = "40001"
    WALLET_NOT_FOUND = "40002"
    INVALID_AMOUNT = "40003"
    WALLET_FROZEN = "40004"

    # ── Product ──────────────────────────────────────────
    PRODUCT_NOT_FOUND = "50001"
    PRODUCT_UNAVAILABLE = "50002"
    PRODUCT_DISCONTINUED = "50003"

    # ── Agent ────────────────────────────────────────────
    AGENT_NOT_FOUND = "60001"
    AGENT_SUSPENDED = "60002"
    INVENTORY_UNAVAILABLE = "60003"
    INVENTORY_EXHAUSTED = "60004"

    # ── Routing ──────────────────────────────────────────
    NO_ROUTE_FOUND = "70001"
    ADAPTER_UNAVAILABLE = "70002"
    ROUTING_TIMEOUT = "70003"

    # ── Third-party ──────────────────────────────────────
    UPSTREAM_TIMEOUT = "80001"
    UPSTREAM_ERROR = "80002"
    CALLBACK_FAILED = "80003"


class AppException(Exception):
    """Base application exception with error code and context."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        message: str = "",
        status_code: int = 400,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message or code.name
        self.status_code = status_code
        self.detail = detail or {}
        super().__init__(self.message)
