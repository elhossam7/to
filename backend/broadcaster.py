from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Set


class Broadcaster:
    def __init__(self) -> None:
        self._subscribers: Set[asyncio.Queue[Dict[str, Any]]] = set()
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[Dict[str, Any]]]:
        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._subscribers.add(queue)
        try:
            yield queue
        finally:
            async with self._lock:
                self._subscribers.discard(queue)

    async def broadcast(self, event: Dict[str, Any]) -> None:
        async with self._lock:
            subscribers = list(self._subscribers)
        stale = []
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                stale.append(queue)
        if stale:
            async with self._lock:
                for queue in stale:
                    self._subscribers.discard(queue)
