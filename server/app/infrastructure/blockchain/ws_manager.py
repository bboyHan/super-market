"""
WebSocket 连接管理器 — 支持广播消息到所有连接的 admin 客户端
"""
from __future__ import annotations
import json
import logging
from typing import Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WSConnectionManager:
    """Manages WebSocket connections and supports broadcasting."""

    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._lock = False  # Simple lock for thread safety

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.add(ws)
        logger.info("WS client connected (%d total)", len(self._connections))

    async def disconnect(self, ws: WebSocket):
        self._connections.discard(ws)
        logger.info("WS client disconnected (%d remaining)", len(self._connections))

    async def broadcast(self, message: dict):
        """Send a message to all connected clients."""
        if not self._connections:
            return
        payload = json.dumps(message, ensure_ascii=False)
        stale = set()
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.add(ws)
        for ws in stale:
            self._connections.discard(ws)

    @property
    def count(self) -> int:
        return len(self._connections)


# Singleton
_manager: WSConnectionManager | None = None


def get_ws_manager() -> WSConnectionManager:
    global _manager
    if _manager is None:
        _manager = WSConnectionManager()
    return _manager
