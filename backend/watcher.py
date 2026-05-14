from __future__ import annotations

import asyncio
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileSystemEventHandler

from backend.pipeline.jobs import ProcessingJob


class InboxHandler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue[ProcessingJob]) -> None:
        self.loop = loop
        self.queue = queue

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() != ".txt":
            return
        job = ProcessingJob(paths=[path], source="watcher", batch_id=path.stem)
        self.loop.call_soon_threadsafe(self.queue.put_nowait, job)
