# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Authenticated WebSocket fan-out backed by PostgreSQL LISTEN/NOTIFY."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress

from fastapi import WebSocket
from psycopg import AsyncConnection

from services.api.app.events import EVENT_CHANNEL
from services.api.app.settings import Settings

LOGGER = logging.getLogger("api.live")


class LiveConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket, *, subprotocol: str | None = None) -> None:
        await websocket.accept(subprotocol=subprotocol)
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        with suppress(ValueError):
            self._connections.remove(websocket)

    async def broadcast(self, event: dict[str, object]) -> None:
        stale: list[WebSocket] = []
        for websocket in tuple(self._connections):
            try:
                await websocket.send_json(event)
            except RuntimeError:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(websocket)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


def psycopg_url(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def bearer_subprotocol_token(header: str | None) -> str | None:
    """Extract ``bearer, <JWT>`` without placing credentials in the request URL."""
    if header is None:
        return None
    protocols = [protocol.strip() for protocol in header.split(",")]
    if len(protocols) != 2 or protocols[0].lower() != "bearer":
        return None
    token = protocols[1]
    if not token or len(token) > 4096:
        return None
    return token


async def listen_for_events(
    settings: Settings,
    manager: LiveConnectionManager,
    stop_event: asyncio.Event,
) -> None:
    if not settings.database_url.startswith("postgresql"):
        await stop_event.wait()
        return

    delay_s = 1.0
    while not stop_event.is_set():
        try:
            connection = await AsyncConnection.connect(
                psycopg_url(settings.database_url), autocommit=True
            )
            async with connection:
                async with connection.cursor() as cursor:
                    await cursor.execute(f"LISTEN {EVENT_CHANNEL}")
                delay_s = 1.0
                async for notification in connection.notifies(timeout=5):
                    if stop_event.is_set():
                        break
                    payload = json.loads(notification.payload)
                    if isinstance(payload, dict):
                        await manager.broadcast(payload)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            LOGGER.warning("live event listener reconnecting: %s", type(exc).__name__)
            with suppress(TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=delay_s)
            delay_s = min(delay_s * 2, 30.0)
