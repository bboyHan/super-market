from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

from loguru import logger


def generate_signature(
    payload: dict[str, Any],
    secret: str,
    timestamp: int | None = None,
) -> str:
    """Generate an HMAC-SHA256 signature for the payload.

    Args:
        payload: Request data to sign (dict).
        secret: Shared secret key.
        timestamp: Unix timestamp (ms). Uses current time if not provided.

    Returns:
        Hex-encoded signature string.
    """
    ts = timestamp or int(time.time() * 1000)
    sorted_keys = sorted(payload.keys())
    message_parts = [f"{k}={payload[k]}" for k in sorted_keys]
    message_parts.append(f"timestamp={ts}")
    message = "&".join(message_parts)

    signature = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return signature


def verify_signature(
    payload: dict[str, Any],
    secret: str,
    signature: str,
    timestamp: int,
    max_age_ms: int = 60_000,
) -> bool:
    """Verify an HMAC-SHA256 signature.

    Args:
        payload: Original request data.
        secret: Shared secret key.
        signature: Supplied signature to verify.
        timestamp: Unix timestamp (ms) from the request.
        max_age_ms: Maximum allowed age of the signature (default: 60s).

    Returns:
        True if the signature is valid and not expired.
    """
    now = int(time.time() * 1000)
    if now - timestamp > max_age_ms:
        logger.warning("Signature expired | age={}ms", now - timestamp)
        return False

    expected = generate_signature(payload, secret, timestamp)
    return hmac.compare_digest(expected, signature)
