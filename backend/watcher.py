from __future__ import annotations

import asyncio
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileSystemEventHandler


class InboxHandler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue[Path]) -> None:
        self.loop = loop
        self.queue = queue

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() != ".txt":
            return
        self.loop.call_soon_threadsafe(self.queue.put_nowait, path)
