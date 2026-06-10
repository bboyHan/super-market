"""Agent Terminal — Collector router.

Provides status and pipeline control endpoints for the new
three-pipeline collector architecture (browser / PC game / mobile).
"""

import json
import logging
import os
import subprocess
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/collector", tags=["collector"])

# ── In-memory collector state ──
_state = {
    "browser": {"active": False, "count": 0},
    "pcgame": {"active": False, "count": 0, "pid": None},
    "mobile": {"active": False, "count": 0},
    "total_count": 0,
    "started_at": None,
}

_mitm_process: Optional[subprocess.Popen] = None


# ═══════════════════════════════════════════
# Models
# ═══════════════════════════════════════════

class CaptureRequest(BaseModel):
    type: str = "payment_url"
    value: str
    platform: str = "qq_midas"
    product: str = "Q币"
    source: str = "postmessage"
    origin: str = ""
    url: str = ""
    captured_at: str = ""


# ═══════════════════════════════════════════
# Status
# ═══════════════════════════════════════════

@router.get("/status")
async def get_status():
    """Return current collector pipeline status."""
    return {
        "browser": _state["browser"],
        "pcgame": _state["pcgame"],
        "mobile": _state["mobile"],
        "backend": True,
        "platform": bool(settings.AGENT_TOKEN or settings.PLATFORM_API_BASE),
        "totalCount": _state["total_count"],
    }


# ═══════════════════════════════════════════
# Capture endpoint (called by Electron preload or external)
# ═══════════════════════════════════════════

@router.post("/capture")
async def capture_credential(req: CaptureRequest):
    """Receive a captured credential from any pipeline."""
    _state["total_count"] += 1
    _state["browser"]["count"] += 1

    # Save to DB
    try:
        from storage.db import get_cursor
        resource_id = f"at_{int(time.time())}_{_state['total_count']}"
        with get_cursor() as c:
            c.execute(
                "INSERT INTO resources (resource_id, task_id, platform, product_id, "
                "resource_type, value, status, metadata, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (resource_id, "auto_collect", req.platform, "",
                 req.type, req.value[:10000],
                 "collected", json.dumps(req.dict(), ensure_ascii=False),
                 datetime.utcnow().isoformat() + "Z"),
            )
        logger.info(f"[Collector] #{_state['total_count']} {req.product} | {req.type}")
        return {"ok": True, "resource_id": resource_id}
    except Exception as e:
        logger.warning(f"[Collector] DB save failed: {e}")
        return {"ok": True, "note": "captured but not saved"}


# ═══════════════════════════════════════════
# Pipeline control
# ═══════════════════════════════════════════

@router.post("/browser/start")
async def start_browser_pipeline():
    """Start browser pipeline (handled by Electron, just mark active here)."""
    _state["browser"]["active"] = True
    if not _state["started_at"]:
        _state["started_at"] = datetime.utcnow().isoformat() + "Z"
    return {"ok": True}


@router.post("/browser/stop")
async def stop_browser_pipeline():
    _state["browser"]["active"] = False
    return {"ok": True}


@router.post("/pcgame/start")
async def start_pcgame_pipeline():
    """Start mitmproxy for PC game traffic capture."""
    global _mitm_process
    if _mitm_process:
        raise HTTPException(400, "mitmproxy already running")

    mitm_path = _find_mitmdump()
    script_path = os.path.join(os.path.dirname(__file__), "..", "mitmproxy", "pay_collector.py")

    try:
        _mitm_process = subprocess.Popen(
            [mitm_path, "-s", script_path,
             "--listen-host", "0.0.0.0",
             "--listen-port", "8802",
             "--ssl-insecure"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _state["pcgame"]["active"] = True
        _state["pcgame"]["pid"] = _mitm_process.pid
        logger.info("[Collector] mitmproxy started on :8802")
        return {"ok": True, "pid": _mitm_process.pid}
    except FileNotFoundError:
        raise HTTPException(500, "mitmdump not found")


@router.post("/pcgame/stop")
async def stop_pcgame_pipeline():
    global _mitm_process
    if _mitm_process:
        _mitm_process.kill()
        _mitm_process = None
    _state["pcgame"]["active"] = False
    _state["pcgame"]["pid"] = None
    return {"ok": True}


@router.post("/mobile/start")
async def start_mobile_pipeline():
    """Start WiFi hotspot + mitmproxy for mobile capture."""
    # First ensure mitmproxy is running
    global _mitm_process
    if not _mitm_process:
        mitm_path = _find_mitmdump()
        script_path = os.path.join(os.path.dirname(__file__), "..", "mitmproxy", "pay_collector.py")
        try:
            _mitm_process = subprocess.Popen(
                [mitm_path, "-s", script_path,
                 "--listen-host", "0.0.0.0",
                 "--listen-port", "8802",
                 "--ssl-insecure"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            raise HTTPException(500, "mitmdump not found")

    # Try to enable Windows hotspot
    try:
        subprocess.run(
            ["netsh", "wlan", "set", "hostednetwork", "mode=allow",
             "ssid=AgentTerminal", "key=agent8888"],
            capture_output=True, timeout=5,
        )
        subprocess.run(
            ["netsh", "wlan", "start", "hostednetwork"],
            capture_output=True, timeout=5,
        )
        logger.info("[Collector] WiFi hotspot started")
    except Exception as e:
        logger.warning(f"[Collector] Hotspot may have failed: {e}")

    _state["mobile"]["active"] = True
    return {"ok": True, "note": "Hotspot: AgentTerminal / agent8888"}


@router.post("/mobile/stop")
async def stop_mobile_pipeline():
    try:
        subprocess.run(["netsh", "wlan", "stop", "hostednetwork"],
                       capture_output=True, timeout=5)
    except Exception:
        pass
    _state["mobile"]["active"] = False
    return {"ok": True}


# ═══════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════

def _find_mitmdump() -> str:
    """Find mitmdump binary in bundled locations."""
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "mitmproxy", "mitmdump"),
        os.path.join(os.path.dirname(__file__), "..", "mitmproxy", "mitmdump.exe"),
        "mitmdump",
    ]
    for c in candidates:
        if os.path.isfile(c) or c == "mitmdump":
            return c
    return "mitmdump"  # fallback to PATH
