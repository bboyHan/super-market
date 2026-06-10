"""凭证处理器链 — 采集后的处理流水线。

每个凭证经过的处理器（按顺序）：
  1. DedupProcessor — 按 value 去重
  2. ClassifierProcessor — 平台适配器精确归类 + 匹配货品
  3. StorageProcessor — 写入 SQLite
  4. UploadProcessor — 异步上传到平台
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

from models import Credential, CredentialStatus
from storage.db import get_cursor, add_log

logger = logging.getLogger("agent-terminal.processors")


class BaseProcessor(ABC):
    """处理器基类。"""

    @abstractmethod
    async def process(self, credential: Credential) -> Credential:
        ...


# ── 1. 去重处理器 ────────────────────────────────


class DedupProcessor(BaseProcessor):
    """按凭证 value 的 SHA256 去重。"""

    def __init__(self):
        self._seen_hashes: set[str] = set()

    async def process(self, credential: Credential) -> Credential:
        value_hash = hashlib.sha256(credential.value.encode()).hexdigest()
        if value_hash in self._seen_hashes:
            credential.status = CredentialStatus.DUPLICATED
            logger.debug(f"Duplicate credential dropped: {credential.short_id}")
        else:
            self._seen_hashes.add(value_hash)
        return credential


# ── 2. 归类处理器 ────────────────────────────────


class ClassifierProcessor(BaseProcessor):
    """使用平台适配器精确归类凭证，匹配到对应的货品 ID。"""

    def __init__(self, platform_adapters: list):
        self._adapters = platform_adapters

    async def process(self, credential: Credential) -> Credential:
        if credential.status == CredentialStatus.DUPLICATED:
            return credential

        # 如果已有平台信息但不完整，尝试适配器再次识别
        raw_data = credential.raw_data or {}
        for adapter in self._adapters:
            if adapter.match(raw_data):
                result = adapter.extract(raw_data)
                if result:
                    if result.get("type"):
                        from models import CredentialType
                        credential.type = CredentialType(result["type"])
                    if result.get("product_id"):
                        credential.product_id = result["product_id"]
                    if result.get("metadata"):
                        credential.metadata.update(result["metadata"])
                    credential.platform = adapter.platform_name
                    break

        credential.status = CredentialStatus.VALIDATED
        return credential


# ── 3. 存储处理器 ────────────────────────────────


class StorageProcessor(BaseProcessor):
    """将凭证写入本地 SQLite 数据库。"""

    async def process(self, credential: Credential) -> Credential:
        if credential.status in (CredentialStatus.DUPLICATED, CredentialStatus.REJECTED):
            return credential

        cred_dict = credential.to_dict()

        with get_cursor() as cursor:
            cursor.execute(
                """INSERT OR IGNORE INTO resources
                   (resource_id, task_id, platform, product_id, resource_type, value, status, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    credential.id,
                    "capture_engine",  # 捕获引擎统一入口
                    credential.platform,
                    credential.product_id,
                    credential.type.value,
                    credential.value,
                    credential.status.value,
                    json.dumps(cred_dict.get("metadata", {}), ensure_ascii=False),
                    credential.captured_at,
                ),
            )

        add_log("info", credential.source_pipeline or "capture",
                f"凭证已存储: {credential.type.value} ({credential.platform})")

        return credential


# ── 4. 上传处理器 ────────────────────────────────


class UploadProcessor(BaseProcessor):
    """异步将凭证上传到 Super Market 平台。

    使用队列 + 后台 Worker 实现非阻塞上传。
    上传成功后更新本地状态为 uploaded。
    """

    def __init__(self, platform_base: str, token_getter):
        self._platform_base = platform_base
        self._get_token = token_getter
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """启动后台上传 Worker。"""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Upload processor worker started")

    async def stop(self):
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    async def process(self, credential: Credential) -> Credential:
        if credential.status not in (CredentialStatus.VALIDATED, CredentialStatus.COLLECTED):
            return credential
        # 入队等待上传
        await self._queue.put(credential)
        return credential

    async def _worker_loop(self):
        """后台 Worker：从队列取出凭证并上传。"""
        import httpx
        from config import settings
        from storage.db import get_setting

        while self._running:
            try:
                credential = await asyncio.wait_for(self._queue.get(), timeout=5)
            except asyncio.TimeoutError:
                continue

            try:
                token = self._get_token() or ""
                headers = {"Content-Type": "application/json"}
                if token:
                    headers["Authorization"] = f"Bearer {token}"

                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        f"{self._platform_base}/api/terminal/inventory/upload",
                        json={
                            "items": [{
                                "product_id": int(credential.product_id) if credential.product_id.isdigit() else 0,
                                "content": credential.value,
                                "expires_at": credential.expires_at or "",
                            }],
                        },
                        headers=headers,
                    )

                    if resp.status_code in (200, 201):
                        data = resp.json()
                        if data.get("code") == 0:
                            credential.status = CredentialStatus.UPLOADED
                            with get_cursor() as c:
                                c.execute(
                                    "UPDATE resources SET status='uploaded', uploaded_at=? WHERE resource_id=?",
                                    (datetime.now(timezone.utc).isoformat(), credential.id),
                                )
                            add_log("info", "upload", f"凭证上传成功: {credential.short_id}")
                        else:
                            logger.warning(f"Upload failed (business): {data.get('msg')}")
                    else:
                        logger.warning(f"Upload failed (HTTP {resp.status_code})")

            except Exception as e:
                logger.error(f"Upload error: {e}")

            finally:
                self._queue.task_done()


# ── 处理器链 ────────────────────────────────────


class ProcessorChain:
    """处理器链 — 按顺序执行所有处理器。"""

    def __init__(self):
        self._processors: list[BaseProcessor] = []

    def add(self, processor: BaseProcessor):
        self._processors.append(processor)

    async def process(self, credential: Credential) -> Credential:
        for proc in self._processors:
            credential = await proc.process(credential)
            if credential.status in (CredentialStatus.DUPLICATED, CredentialStatus.REJECTED):
                # 重复或拒绝的凭证不再继续处理
                break
        return credential
