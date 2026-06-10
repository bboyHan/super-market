"""Data models for Agent Terminal."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Task:
    """Represents a collection task."""

    id: int
    task_id: str
    platform: str
    product_id: str
    quantity: int
    method: str  # browser / emulator / cdp / manual
    auto_mode: str  # full / semi / assisted
    account_id: Optional[str]
    status: str  # pending / running / paused / completed / failed / cancelled
    progress: int = 0
    current_step: str = ""
    error_message: Optional[str] = None
    result: Optional[str] = None  # JSON string of collected resources
    created_at: str = ""
    updated_at: str = ""
    completed_at: Optional[str] = None


@dataclass
class Resource:
    """Represents a collected resource (credential, link, etc.)."""

    id: int
    resource_id: str
    task_id: str
    platform: str
    product_id: str
    resource_type: str  # payment_link / qr_code / credential / cookie
    value: str  # encrypted or plain
    status: str  # collected / uploaded / expired / failed
    expires_at: Optional[str] = None
    metadata: Optional[str] = None  # JSON string
    created_at: str = ""
    uploaded_at: Optional[str] = None


@dataclass
class Account:
    """Represents a third-party platform account."""

    id: int
    account_id: str
    platform: str
    name: str
    cookie_encrypted: str  # AES-256-GCM encrypted cookie
    cookie_valid: bool = False
    last_checked_at: Optional[str] = None
    note: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class LogEntry:
    """Represents a log entry for SSE streaming."""

    id: int
    level: str  # info / warning / error / debug
    source: str  # task_id or "system"
    message: str
    created_at: str = ""
