"""System operations API router."""

import asyncio
import subprocess
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings
from services import task_manager
from storage.db import get_cursor, add_log

router = APIRouter(prefix="/api/system", tags=["system"])

# System state
_start_time = time.time()
_emulator_process = None


# --- Models ---

class SystemStatusResponse(BaseModel):
    browser_available: bool
    emulator_running: bool
    platform_connected: bool
    uptime_seconds: float
    active_tasks: int
    python_version: Optional[str] = None
    playwright_installed: bool = False
    mitmproxy_installed: bool = False


class EmulatorOperationResponse(BaseModel):
    success: bool
    message: str


# --- Endpoints ---

@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status():
    """Get overall system status including browser, emulator, and platform connection."""
    uptime = time.time() - _start_time
    active = task_manager.get_active_count()

    # Check browser availability
    browser_available = False
    playwright_installed = False
    try:
        import playwright
        playwright_installed = True
        # Check if browsers are installed
        from playwright._repo_version import version as pw_version
        browser_available = True
    except (ImportError, Exception):
        pass

    # Check mitmproxy
    mitmproxy_installed = False
    try:
        import mitmproxy
        mitmproxy_installed = True
    except ImportError:
        pass

    # Check emulator
    emulator_running = _emulator_process is not None and _emulator_process.poll() is None

    # Quick platform connectivity check
    platform_connected = False
    try:
        import httpx
        resp = httpx.get(
            f"{settings.PLATFORM_API_BASE}/api/v1/health",
            timeout=3,
        )
        platform_connected = resp.status_code == 200
    except Exception:
        pass

    import sys

    return SystemStatusResponse(
        browser_available=browser_available,
        emulator_running=emulator_running,
        platform_connected=platform_connected,
        uptime_seconds=uptime,
        active_tasks=active,
        python_version=sys.version.split()[0],
        playwright_installed=playwright_installed,
        mitmproxy_installed=mitmproxy_installed,
    )


@router.post("/emulator/start", response_model=EmulatorOperationResponse)
async def start_emulator():
    """Start the Android emulator."""
    global _emulator_process

    if _emulator_process is not None and _emulator_process.poll() is None:
        return EmulatorOperationResponse(
            success=True,
            message="Emulator is already running",
        )

    try:
        _emulator_process = subprocess.Popen(
            ["emulator", "-avd", "agent_terminal", "-no-window"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        add_log("info", "system", "Emulator start command issued")
        return EmulatorOperationResponse(
            success=True,
            message="Emulator start command issued. It may take a moment to boot.",
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Emulator command not found. Ensure Android SDK is installed and 'emulator' is in PATH.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/emulator/stop", response_model=EmulatorOperationResponse)
async def stop_emulator():
    """Stop the Android emulator."""
    global _emulator_process

    if _emulator_process is None or _emulator_process.poll() is not None:
        return EmulatorOperationResponse(
            success=True,
            message="Emulator is not running",
        )

    try:
        # Try graceful shutdown via adb first
        subprocess.run(
            ["adb", "emu", "kill"],
            capture_output=True,
            timeout=10,
        )
        _emulator_process.terminate()
        try:
            _emulator_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _emulator_process.kill()
        _emulator_process = None

        add_log("info", "system", "Emulator stopped")
        return EmulatorOperationResponse(
            success=True,
            message="Emulator stopped successfully",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/emulator/status", response_model=EmulatorOperationResponse)
async def get_emulator_status():
    """Get the current status of the Android emulator."""
    global _emulator_process

    if _emulator_process is None:
        return EmulatorOperationResponse(
            success=False,
            message="Emulator is not running",
        )

    return_code = _emulator_process.poll()
    if return_code is None:
        return EmulatorOperationResponse(
            success=True,
            message="Emulator is running",
        )
    else:
        _emulator_process = None
        return EmulatorOperationResponse(
            success=False,
            message=f"Emulator exited with code {return_code}",
        )
