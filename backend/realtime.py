import asyncio
import os
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from psycopg import AsyncConnection


def _expected_api_key() -> str:
    return os.environ.get("STIGMER_API_KEY", "")


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is required for realtime")
    return url


class BoardWsHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._listen_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def add(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.add(ws)
            if self._listen_task is None or self._listen_task.done():
                self._listen_task = asyncio.create_task(self._listen())

    async def remove(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def _broadcast_json(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            clients = list(self._clients)
        if not clients:
            return

        async def _send(ws: WebSocket) -> bool:
            try:
                await asyncio.wait_for(ws.send_json(payload), timeout=1.5)
                return True
            except Exception:
                return False

        results = await asyncio.gather(*(_send(ws) for ws in clients), return_exceptions=True)
        dead = [ws for ws, ok in zip(clients, results, strict=True) if ok is not True]
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    async def _listen(self) -> None:
        while True:
            async with self._lock:
                if not self._clients:
                    self._listen_task = None
                    return
            try:
                async with await AsyncConnection.connect(
                    _database_url(),
                    autocommit=True,
                ) as conn:
                    async with conn.cursor() as cur:
                        await cur.execute('LISTEN "board.changed";')
                    while True:
                        notify = await conn.notifies.get()
                        payload = {"type": "board.changed", "payload": notify.payload}
                        await self._broadcast_json(payload)
            except Exception:
                await asyncio.sleep(0.5)


HUB = BoardWsHub()


def register_realtime(app: FastAPI) -> None:
    @app.websocket("/ws/board")
    async def ws_board(ws: WebSocket):
        api_key = ws.query_params.get("api_key")
        expected = _expected_api_key()
        if not expected or api_key != expected:
            await ws.close(code=1008)
            return
        await ws.accept()
        await HUB.add(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            await HUB.remove(ws)
