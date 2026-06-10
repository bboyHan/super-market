from __future__ import annotations

import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger


class TerminalConnectionManager:
    """Manages WebSocket connections from terminal devices."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}
        self._agent_map: dict[str, str] = {}  # agent_id -> session_id

    async def connect(self, agent_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        session_id = f"{agent_id}_{id(websocket)}"
        self._connections[session_id] = websocket
        self._agent_map[agent_id] = session_id
        logger.info("Terminal connected | agent={} session={}", agent_id, session_id)

    def disconnect(self, agent_id: str) -> None:
        session_id = self._agent_map.pop(agent_id, "")
        self._connections.pop(session_id, None)
        logger.info("Terminal disconnected | agent={}", agent_id)

    async def send_to_agent(self, agent_id: str, payload: dict[str, Any]) -> bool:
        """Send a JSON message to a specific agent. Returns True on success."""
        session_id = self._agent_map.get(agent_id)
        if not session_id:
            logger.warning("Agent not connected | agent={}", agent_id)
            return False
        ws = self._connections.get(session_id)
        if not ws:
            return False
        try:
            await ws.send_json(payload)
            return True
        except Exception:
            logger.exception("Send failed | agent={}", agent_id)
            self.disconnect(agent_id)
            return False

    async def broadcast(self, payload: dict[str, Any]) -> None:
        """Broadcast a message to all connected terminals."""
        for agent_id in list(self._agent_map.keys()):
            await self.send_to_agent(agent_id, payload)

    @property
    def connected_agents(self) -> list[str]:
        return list(self._agent_map.keys())

    @property
    def active_count(self) -> int:
        return len(self._connections)


# Module-level singleton
manager = TerminalConnectionManager()


async def terminal_ws_handler(websocket: WebSocket, agent_id: str) -> None:
    """WebSocket endpoint for terminal devices."""
    await manager.connect(agent_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            logger.debug("Terminal msg | agent={} data={}", agent_id, message)
            # TODO: route message to appropriate handler
            await websocket.send_json({"status": "ok", "echo": message})
    except WebSocketDisconnect:
        manager.disconnect(agent_id)
    except Exception:
        logger.exception("WebSocket error | agent={}", agent_id)
        manager.disconnect(agent_id)
