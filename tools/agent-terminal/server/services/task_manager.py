"""Task orchestration service - manages concurrent collection tasks."""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Callable, Optional

from config import settings
from collectors.base import BaseCollector
from collectors.browser import BrowserCollector
from collectors.emulator import EmulatorCollector
from collectors.manual import ManualCollector
from collectors.qq_coin import QQCoinCollector
from storage.db import get_cursor, add_log

# In-memory task registry
_tasks: dict[str, dict[str, Any]] = {}
_task_events: dict[str, list[dict]] = {}
_sse_queues: list[asyncio.Queue] = []

# Locks
_active_tasks: dict[str, asyncio.Task] = {}
_task_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_TASKS)


async def broadcast_event(event: dict):
    """Broadcast an event to all SSE listeners."""
    for queue in _sse_queues:
        await queue.put(event)


def get_collector(task_id: str, config: dict) -> BaseCollector:
    """Factory function to get the appropriate collector for a task."""
    method = config.get("method", "browser")
    platform = config.get("platform", "")

    if platform == "qq_coin":
        return QQCoinCollector(task_id, config)
    elif method == "browser" or method == "cdp":
        return BrowserCollector(task_id, config)
    elif method == "emulator":
        return EmulatorCollector(task_id, config)
    elif method == "manual":
        return ManualCollector(task_id, config)
    else:
        raise ValueError(f"Unknown collection method: {method}")


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


async def run_collection_task(task_id: str) -> None:
    """Run a collection task in the background."""
    task_info = _tasks.get(task_id)
    if not task_info:
        return

    config = task_info["config"]
    collector = get_collector(task_id, config)

    # Register collector for external input injection
    _active_collectors[task_id] = collector

    try:
        async with _task_semaphore:
            task_info["status"] = "running"
            task_info["updated_at"] = _now()

            with get_cursor() as cursor:
                cursor.execute(
                    "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
                    ("running", _now(), task_id),
                )

            await broadcast_event({
                "type": "task_update",
                "task_id": task_id,
                "status": "running",
            })
            add_log("info", task_id, f"Task {task_id} started (method={config.get('method')})")

            last_step_data = {}
            async for step_event in collector.execute():
                step = step_event.get("step", "")
                status = step_event.get("status", "running")
                message = step_event.get("message", "")
                progress = step_event.get("progress", 0)

                # Update task state
                task_info["progress"] = progress
                task_info["current_step"] = step

                # Store step data if present
                if "data" in step_event:
                    last_step_data = step_event["data"]
                    # Persist qr_image to task info for frontend polling
                    if "qr_image" in step_event["data"]:
                        task_info["qr_image"] = step_event["data"]["qr_image"]

                with get_cursor() as cursor:
                    cursor.execute(
                        "UPDATE tasks SET progress = ?, current_step = ?, updated_at = ? WHERE task_id = ?",
                        (progress, step, _now(), task_id),
                    )

                # Broadcast step event
                await broadcast_event({
                    "type": "task_step",
                    "task_id": task_id,
                    "step": step,
                    "status": status,
                    "message": message,
                    "progress": progress,
                })

                # Log significant events
                if status in ("completed", "failed"):
                    add_log(
                        "info" if status == "completed" else "error",
                        task_id,
                        f"Step '{step}': {message}",
                    )

                # Store error message
                if status == "failed":
                    task_info["error_message"] = message
                    with get_cursor() as cursor:
                        cursor.execute(
                            "UPDATE tasks SET error_message = ?, updated_at = ? WHERE task_id = ?",
                            (message, _now(), task_id),
                        )

            # Task completed
            if collector._cancelled:
                final_status = "cancelled"
            elif last_step_data.get("resources") is not None:
                final_status = "completed"
            else:
                final_status = "failed"

            task_info["status"] = final_status
            task_info["completed_at"] = _now()

            # Save resources to database
            resources = last_step_data.get("resources", [])
            if resources:
                task_info["result"] = json.dumps(resources)
                _save_resources(task_id, config, resources)

            with get_cursor() as cursor:
                cursor.execute(
                    "UPDATE tasks SET status = ?, result = ?, completed_at = ?, updated_at = ? WHERE task_id = ?",
                    (final_status, task_info.get("result"), _now(), _now(), task_id),
                )

            await broadcast_event({
                "type": "task_update",
                "task_id": task_id,
                "status": final_status,
            })
            add_log("info", task_id, f"Task {task_id} {final_status}")

    except Exception as e:
        task_info["status"] = "failed"
        task_info["error_message"] = str(e)

        with get_cursor() as cursor:
            cursor.execute(
                "UPDATE tasks SET status = ?, error_message = ?, updated_at = ? WHERE task_id = ?",
                ("failed", str(e), _now(), task_id),
            )

        await broadcast_event({
            "type": "task_update",
            "task_id": task_id,
            "status": "failed",
            "error": str(e),
        })
        add_log("error", task_id, f"Task {task_id} failed: {e}")

    finally:
        await collector.cleanup()
        _active_tasks.pop(task_id, None)
        _active_collectors.pop(task_id, None)


def _save_resources(task_id: str, config: dict, resources: list[dict]):
    """Save collected resources to the database."""
    platform = config.get("platform", "")
    product_id = config.get("product_id", "")
    now = _now()

    with get_cursor() as cursor:
        for i, res in enumerate(resources):
            resource_id = f"res_{uuid.uuid4().hex[:12]}"
            value = res.get("value", "")
            resource_type = res.get("resource_type", "credential")
            metadata = res.get("metadata", "{}")

            cursor.execute(
                """INSERT INTO resources 
                   (resource_id, task_id, platform, product_id, resource_type, value, status, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (resource_id, task_id, platform, product_id, resource_type, value, "collected", metadata, now),
            )


def create_task(config: dict) -> str:
    """Create a new collection task and start it in the background."""
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    now = _now()

    task_info = {
        "task_id": task_id,
        "config": config,
        "platform": config.get("platform", ""),
        "product_id": config.get("product_id", ""),
        "quantity": config.get("quantity", 1),
        "method": config.get("method", "browser"),
        "auto_mode": config.get("auto_mode", "semi"),
        "account_id": config.get("account_id"),
        "status": "pending",
        "progress": 0,
        "current_step": "",
        "error_message": None,
        "result": None,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }
    _tasks[task_id] = task_info

    # Persist to database
    with get_cursor() as cursor:
        cursor.execute(
            """INSERT INTO tasks 
               (task_id, platform, product_id, quantity, method, auto_mode, account_id, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task_id,
                config.get("platform", ""),
                config.get("product_id", ""),
                config.get("quantity", 1),
                config.get("method", "browser"),
                config.get("auto_mode", "semi"),
                config.get("account_id"),
                "pending",
                now,
                now,
            ),
        )

    add_log("info", task_id, f"Task {task_id} created: {config.get('platform')}/{config.get('product_id')}")

    # Start execution in background
    bg_task = asyncio.create_task(run_collection_task(task_id))
    _active_tasks[task_id] = bg_task

    return task_id


def get_task(task_id: str) -> Optional[dict]:
    """Get task info by ID."""
    task = _tasks.get(task_id)
    if task:
        return task
    # Fallback to database
    with get_cursor() as cursor:
        row = cursor.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        if row:
            return dict(row)
    return None


def list_tasks(status_filter: Optional[str] = None) -> list[dict]:
    """List all tasks, optionally filtered by status."""
    with get_cursor() as cursor:
        if status_filter:
            rows = cursor.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY id DESC",
                (status_filter,),
            ).fetchall()
        else:
            rows = cursor.execute(
                "SELECT * FROM tasks ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def update_task_status(task_id: str, status: str) -> bool:
    """Update a task's status."""
    task = _tasks.get(task_id)
    if not task:
        return False

    now = _now()
    task["status"] = status
    task["updated_at"] = now

    with get_cursor() as cursor:
        cursor.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
            (status, now, task_id),
        )

    add_log("info", task_id, f"Task {task_id} set to {status}")

    # If cancelling, cancel the collector
    if status == "cancelled":
        active_task = _active_tasks.get(task_id)
        if active_task:
            active_task.cancel()

    return True


async def pause_task(task_id: str) -> bool:
    """Pause a running task."""
    task = _tasks.get(task_id)
    if not task or task["status"] != "running":
        return False
    return update_task_status(task_id, "paused")


async def resume_task(task_id: str) -> bool:
    """Resume a paused task."""
    task = _tasks.get(task_id)
    if not task or task["status"] != "paused":
        return False
    return update_task_status(task_id, "running")


async def cancel_task(task_id: str) -> bool:
    """Cancel a task."""
    task = _tasks.get(task_id)
    if not task:
        return False
    return update_task_status(task_id, "cancelled")


async def provide_input(task_id: str, values: list[str]) -> bool:
    """Provide manual input values to a task waiting for user input.

    Finds the task's collector (must be ManualCollector), calls its
    provide_input method, and resumes the task's asyncio.Task.
    """
    task_info = _tasks.get(task_id)
    if not task_info:
        return False

    # Verify the task is in the running state and awaiting input
    if task_info.get("status") != "running":
        return False

    # Find the active asyncio task
    bg_task = _active_tasks.get(task_id)
    if not bg_task:
        return False

    # The collector is already instantiated inside run_collection_task,
    # but we need access to set its pending values. We store a reference.
    # We'll look up the collector instance via the active task.
    # Alternative: store the collector reference in _active_collectors dict

    # Quick approach: For the manual collector, we re-run it by setting
    # the config values and restarting. But the better approach is to
    # store a reference to the collector.

    # We'll use a global collector registry for this.
    collector = _active_collectors.get(task_id)
    if not collector:
        return False

    if not hasattr(collector, "provide_input"):
        return False

    collector.provide_input(values)
    return True


# Collector registry for external input injection
_active_collectors: dict[str, BaseCollector] = {}


def get_active_count() -> int:
    """Get count of currently running tasks."""
    return len(_active_tasks)
