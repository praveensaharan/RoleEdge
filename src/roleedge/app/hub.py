"""Live updates: every screen showing a circle (the caregiver's workspace and the parent's phone) gets each change."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class Hub:
    def __init__(self) -> None:
        self._sockets: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def join(self, circle_id: str, socket: WebSocket) -> None:
        await socket.accept()
        async with self._lock:
            self._sockets[circle_id].add(socket)

    async def leave(self, circle_id: str, socket: WebSocket) -> None:
        async with self._lock:
            self._sockets[circle_id].discard(socket)

    async def send(self, circle_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            sockets = list(self._sockets[circle_id])
        for socket in sockets:
            try:
                await socket.send_json(event)
            except Exception:  # a closed tab; forget it
                await self.leave(circle_id, socket)
