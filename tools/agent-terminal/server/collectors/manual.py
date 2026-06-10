"""Manual entry collector for user-pasted links, QR codes, and card keys."""

import asyncio
import json
import re
import uuid
from typing import Any, AsyncGenerator, Optional

import httpx

from collectors.base import BaseCollector
from config import settings
from storage.db import get_cursor, get_setting


def _now() -> str:
    from datetime import datetime
    return datetime.utcnow().isoformat() + "Z"


def _detect_type(value: str) -> str:
    """Detect the resource type from a raw user-pasted value."""
    value = value.strip()
    # HTTP/HTTPS URL → payment_link
    if value.startswith("http://") or value.startswith("https://"):
        return "payment_link"
    # data:image or base64 QR → qrcode
    if value.startswith("data:image/") or value.startswith("data:image;") or value.startswith("qr:"):
        return "qrcode"
    # Card key format (e.g., JD-XXXX-XXXX, or xx-xxxx-xxxx-xxxx)
    if re.match(r'^[A-Za-z0-9]{2,8}[-_][A-Za-z0-9]{4,8}[-_][A-Za-z0-9]{4,8}', value):
        return "card_key"
    # Length > 10 → unknown (likely credential)
    if len(value) > 10:
        return "unknown"
    return "unknown"


class ManualCollector(BaseCollector):
    """Collects credentials provided manually by the user (paste links, QR codes, card keys)."""

    def __init__(self, task_id: str, config: dict[str, Any]):
        super().__init__(task_id, config)
        self._pending_values: list[str] = []
        self._input_event = asyncio.Event()

    @property
    def name(self) -> str:
        return "manual"

    def provide_input(self, values: list[str]) -> None:
        """Called externally to feed user-pasted values into the collector."""
        self._pending_values = values
        self._input_event.set()

    async def execute(self) -> AsyncGenerator[dict, None]:
        """Execute manual credential entry with full validation and upload flow."""
        config = self.config
        platform = config.get("platform", "unknown")
        product_id = config.get("product_id", "")
        quantity = config.get("quantity", 1)

        try:
            # Step 1: Wait for user input
            yield {
                "step": "await_input",
                "status": "running",
                "message": f"Waiting for manual input of {quantity} credential(s) for {platform} product {product_id}...",
                "progress": 10,
                "data": {
                    "input_type": "url_or_qrcode",
                    "expected_count": quantity,
                    "platform": platform,
                    "product_id": product_id,
                },
            }

            # Wait for user input if not pre-provided
            if not self._pending_values:
                yield {
                    "step": "await_input",
                    "status": "running",
                    "message": "Waiting for user to provide credentials...",
                    "progress": 30,
                    "data": {"needs_input": True},
                }
                # Wait for provide_input() to be called
                await self._input_event.wait()
                yield {
                    "step": "await_input",
                    "status": "completed",
                    "message": f"Received {len(self._pending_values)} manual input(s)",
                    "progress": 35,
                }
            else:
                yield {
                    "step": "await_input",
                    "status": "completed",
                    "message": f"Received {len(self._pending_values)} pre-provided input(s)",
                    "progress": 35,
                }

            # Step 2: Validate each input and detect type
            validated = []
            total = len(self._pending_values)
            for i, raw_val in enumerate(self._pending_values):
                if self._cancelled:
                    return

                val = raw_val.strip()
                if not val:
                    continue

                resource_type = _detect_type(val)

                yield {
                    "step": "validate",
                    "status": "running",
                    "message": f"Validating input {i+1}/{total} (detected: {resource_type})...",
                    "progress": 40 + (i * 30 // total),
                }

                validated.append({
                    "value": val,
                    "resource_type": resource_type,
                    "metadata": json.dumps({
                        "platform": platform,
                        "product_id": product_id,
                        "source": "manual_entry",
                    }),
                    "expires_at": None,
                })

            yield {
                "step": "validate",
                "status": "completed",
                "message": f"Validated {len(validated)}/{total} inputs",
                "progress": 70,
            }

            # Step 3: Save each to local SQLite
            yield {
                "step": "save_local",
                "status": "running",
                "message": f"Saving {len(validated)} resources to local database...",
                "progress": 75,
            }

            saved_resources = []
            now = _now()
            for i, res in enumerate(validated):
                if self._cancelled:
                    return
                resource_id = f"res_{uuid.uuid4().hex[:12]}"
                with get_cursor() as cursor:
                    cursor.execute(
                        """INSERT INTO resources
                           (resource_id, task_id, platform, product_id, resource_type, value, status, metadata, expires_at, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            resource_id,
                            self.task_id,
                            platform,
                            product_id,
                            res["resource_type"],
                            res["value"],
                            "collected",
                            res["metadata"],
                            res["expires_at"],
                            now,
                        ),
                    )
                saved_resources.append({**res, "resource_id": resource_id})

            yield {
                "step": "save_local",
                "status": "completed",
                "message": f"Saved {len(saved_resources)} resources locally",
                "progress": 80,
            }

            # Step 4: Upload each to platform via httpx
            yield {
                "step": "upload",
                "status": "running",
                "message": f"Uploading {len(saved_resources)} resources to platform...",
                "progress": 85,
            }

            uploaded_ids = []
            pending_ids = []
            for i, res in enumerate(saved_resources):
                if self._cancelled:
                    return

                yield {
                    "step": "upload",
                    "status": "running",
                    "message": f"Uploading {i+1}/{len(saved_resources)} ({res['resource_type']})...",
                    "progress": 85 + (i * 10 // len(saved_resources)),
                }

                try:
                    # DEBUG
                    rid = str(res.get('resource_id', ''))
                    with open('/tmp/manual_upload_debug.log','a') as f:
                        f.write(f'Upload attempt for {rid}\n')
                    
                    async with httpx.AsyncClient(timeout=30) as client:
                        token = settings.AGENT_TOKEN or get_setting("agent_token", "")
                        headers = {"Content-Type": "application/json"}
                        if token:
                            headers["Authorization"] = f"Bearer {token}"

                        upload_resp = await client.post(
                            f"{settings.PLATFORM_API_BASE}/api/terminal/inventory/upload",
                            json={
                                "items": [{
                                    "product_id": int(product_id) if str(product_id).isdigit() else product_id,
                                    "content": res["value"],
                                    "expires_at": res.get("expires_at") or "",
                                }]
                            },
                            headers=headers,
                            timeout=15,
                        )

                        if upload_resp.status_code in (200, 201):
                            data = upload_resp.json()
                            with open('/tmp/manual_upload_debug.log','a') as f:
                                f.write(f'Upload OK: {json.dumps(data)[:200]}\n')
                            ids = data.get("platform_resource_ids", [])
                            uploaded_ids.extend(ids)
                            # Mark as uploaded locally
                            with get_cursor() as cursor:
                                cursor.execute(
                                    "UPDATE resources SET status = ?, uploaded_at = ? WHERE resource_id = ?",
                                    ("uploaded", _now(), res["resource_id"]),
                                )
                        else:
                            with open('/tmp/manual_upload_debug.log','a') as f:
                                f.write(f'Upload rejected: {upload_resp.status_code} {upload_resp.text[:150]}\n')
                            # Upload failed, mark as pending retry
                            with get_cursor() as cursor:
                                cursor.execute(
                                    "UPDATE resources SET status = ? WHERE resource_id = ?",
                                    ("pending_upload", res["resource_id"]),
                                )
                            pending_ids.append(res["resource_id"])

                except Exception as e:
                    import traceback
                    with open('/tmp/manual_upload_debug.log','a') as f:
                        f.write(f'Upload ERROR: {e}\n{traceback.format_exc()}\n')
                    # Network error, mark as pending retry
                    with get_cursor() as cursor:
                        cursor.execute(
                            "UPDATE resources SET status = ? WHERE resource_id = ?",
                            ("pending_upload", res["resource_id"]),
                        )
                    pending_ids.append(res["resource_id"])

            yield {
                "step": "upload",
                "status": "completed",
                "message": f"Uploaded {len(uploaded_ids)} resources, {len(pending_ids)} pending retry",
                "progress": 95,
            }

            # Step 5: Final summary
            yield {
                "step": "summary",
                "status": "completed",
                "message": f"Manual entry complete: {len(uploaded_ids)} uploaded, {len(pending_ids)} pending",
                "progress": 100,
                "data": {
                    "resources": saved_resources,
                    "uploaded_ids": uploaded_ids,
                    "pending_ids": pending_ids,
                },
            }

        except Exception as e:
            yield {
                "step": "error",
                "status": "failed",
                "message": f"Manual collection failed: {str(e)}",
                "progress": 0,
            }

    async def cleanup(self):
        """No cleanup needed for manual collector."""
        pass
