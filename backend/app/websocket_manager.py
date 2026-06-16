"""
websocket_manager.py - Quản lý các kết nối WebSocket
"""
import asyncio
import logging
from typing import Dict, Set
# pyrefly: ignore [missing-import]
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Quản lý nhiều WebSocket client đồng thời"""

    def __init__(self) -> None:
        # camera_id → set of websockets
        self._rooms: Dict[str, Set[WebSocket]] = {}
        # Tất cả connections
        self._all: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, room: str = "global") -> None:
        await websocket.accept()
        self._all.add(websocket)
        self._rooms.setdefault(room, set()).add(websocket)
        logger.info(f"WS connected – room={room}, total={len(self._all)}")

    def disconnect(self, websocket: WebSocket, room: str = "global") -> None:
        self._all.discard(websocket)
        if room in self._rooms:
            self._rooms[room].discard(websocket)
        logger.info(f"WS disconnected – room={room}, total={len(self._all)}")

    async def broadcast(self, message: dict, room: str = "global") -> None:
        """Gửi JSON tới tất cả client trong room"""
        targets = self._rooms.get(room, set()).copy()
        dead: Set[WebSocket] = set()
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._all.discard(ws)
            self._rooms.get(room, set()).discard(ws)

    async def broadcast_all(self, message: dict) -> None:
        """Gửi tới tất cả client bất kể room"""
        targets = self._all.copy()
        dead: Set[WebSocket] = set()
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._all.discard(ws)

    async def send_personal(self, message: dict, websocket: WebSocket) -> None:
        try:
            await websocket.send_json(message)
        except Exception:
            pass

    def room_size(self, room: str) -> int:
        return len(self._rooms.get(room, set()))

    def total_connections(self) -> int:
        return len(self._all)


# Singleton
manager = ConnectionManager()
