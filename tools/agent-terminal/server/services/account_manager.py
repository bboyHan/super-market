"""Account/cookie management service with encryption."""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Optional

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from config import settings
from storage.db import get_cursor, add_log


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _derive_key(master_key: str, salt: str) -> bytes:
    """Derive an AES-256 key from master key and salt using PBKDF2."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        master_key.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
        dklen=32,
    )


def encrypt_cookie(cookie_data: str) -> str:
    """Encrypt cookie data using AES-256-GCM.

    Returns a JSON string with format: {"ciphertext": "...", "nonce": "...", "tag": "..."}
    """
    key = _derive_key(settings.COOKIE_ENCRYPT_KEY, settings.ENCRYPTION_SALT)
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(cookie_data.encode("utf-8"))
    result = {
        "ciphertext": ciphertext.hex(),
        "nonce": cipher.nonce.hex(),
        "tag": tag.hex(),
    }
    return json.dumps(result)


def decrypt_cookie(encrypted_data: str) -> str:
    """Decrypt AES-256-GCM encrypted cookie data."""
    try:
        data = json.loads(encrypted_data)
        key = _derive_key(settings.COOKIE_ENCRYPT_KEY, settings.ENCRYPTION_SALT)
        cipher = AES.new(
            key,
            AES.MODE_GCM,
            nonce=bytes.fromhex(data["nonce"]),
        )
        plaintext = cipher.decrypt_and_verify(
            bytes.fromhex(data["ciphertext"]),
            bytes.fromhex(data["tag"]),
        )
        return plaintext.decode("utf-8")
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        raise ValueError(f"Failed to decrypt cookie: {e}")


def add_account(platform: str, name: str, cookie: str, note: Optional[str] = None) -> dict:
    """Add a new account with encrypted cookie storage."""
    account_id = f"acct_{uuid.uuid4().hex[:12]}"
    now = _now()
    cookie_encrypted = encrypt_cookie(cookie) if cookie else ""

    with get_cursor() as cursor:
        cursor.execute(
            """INSERT INTO accounts 
               (account_id, platform, name, cookie_encrypted, cookie_valid, created_at, updated_at, note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (account_id, platform, name, cookie_encrypted, 1 if cookie else 0, now, now, note),
        )

    add_log("info", "system", f"Account '{name}' ({platform}) added: {account_id}")

    return {
        "account_id": account_id,
        "platform": platform,
        "name": name,
        "cookie_valid": bool(cookie),
        "note": note,
        "created_at": now,
    }


def list_accounts(platform: Optional[str] = None) -> list[dict]:
    """List all accounts, optionally filtered by platform."""
    with get_cursor() as cursor:
        if platform:
            rows = cursor.execute(
                "SELECT * FROM accounts WHERE platform = ? ORDER BY id DESC",
                (platform,),
            ).fetchall()
        else:
            rows = cursor.execute(
                "SELECT * FROM accounts ORDER BY id DESC"
            ).fetchall()
        accounts = []
        for r in rows:
            acct = dict(r)
            # Don't expose encrypted cookie in list
            acct.pop("cookie_encrypted", None)
            acct["cookie_valid"] = bool(acct.get("cookie_valid", 0))
            accounts.append(acct)
        return accounts


def get_account(account_id: str) -> Optional[dict]:
    """Get account by ID."""
    with get_cursor() as cursor:
        row = cursor.execute(
            "SELECT * FROM accounts WHERE account_id = ?", (account_id,)
        ).fetchone()
        return dict(row) if row else None


def get_account_with_cookie(account_id: str) -> Optional[dict]:
    """Get account with decrypted cookie."""
    account = get_account(account_id)
    if account and account.get("cookie_encrypted"):
        try:
            account["cookie"] = decrypt_cookie(account["cookie_encrypted"])
        except ValueError:
            account["cookie"] = ""
        account.pop("cookie_encrypted", None)
    return account


def delete_account(account_id: str) -> bool:
    """Delete an account by ID."""
    with get_cursor() as cursor:
        cursor.execute("DELETE FROM accounts WHERE account_id = ?", (account_id,))
        deleted = cursor.rowcount > 0
    if deleted:
        add_log("info", "system", f"Account deleted: {account_id}")
    return deleted


def check_cookie_validity(account_id: str) -> dict:
    """Check if an account's cookie is still valid.

    For now, this is a basic placeholder. In production, this would make
    a real API call to the platform with the cookie to verify it's still valid.
    """
    account = get_account(account_id)
    if not account:
        return {"valid": False, "error": "Account not found"}

    now = _now()
    cookie = decrypt_cookie(account["cookie_encrypted"]) if account.get("cookie_encrypted") else ""

    # Basic validation: cookie should not be empty
    valid = bool(cookie) and len(cookie) > 10

    with get_cursor() as cursor:
        cursor.execute(
            "UPDATE accounts SET cookie_valid = ?, last_checked_at = ?, updated_at = ? WHERE account_id = ?",
            (1 if valid else 0, now, now, account_id),
        )

    add_log(
        "info" if valid else "warning",
        "system",
        f"Cookie check for {account.get('name', account_id)}: {'valid' if valid else 'invalid'}",
    )

    return {"valid": valid, "last_checked_at": now}


def refresh_login(account_id: str) -> dict:
    """Trigger a refresh login for an account.

    In production, this would open a browser for re-login or use
    the platform's refresh token flow. Placeholder for now.
    """
    account = get_account(account_id)
    if not account:
        return {"success": False, "error": "Account not found"}

    add_log("info", "system", f"Refresh login triggered for account: {account_id}")

    return {
        "success": True,
        "message": "Refresh login triggered. Please complete login in the browser.",
        "account_id": account_id,
    }
