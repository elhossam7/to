from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict

from backend.broadcaster import Broadcaster
from backend.pipeline.ollama import call_ollama
from backend.pipeline.parser import read_lines
from backend.pipeline.validator import validate_profile
from backend.storage import append_audit, save_profile, utc_now


def source_meta(path: Path) -> Dict[str, Any]:
    try:
        stat = path.stat()
        size = stat.st_size
    except OSError:
        size = None
    return {"filename": path.name, "path": str(path), "size": size}


async def process_file(path: Path, broadcaster: Broadcaster) -> Dict[str, Any]:
    await broadcaster.broadcast({"type": "started", "path": str(path), "filename": path.name, "ts": utc_now()})
    append_audit({"event": "started", "path": str(path)})

    lines = read_lines(path)
    result = await call_ollama(lines)
    profile, warnings = validate_profile(result, path, lines)
    profile["_source"] = {**source_meta(path), "processed_at": utc_now(), "line_count": len(lines)}
    saved_path = save_profile(profile["id"], profile)

    done = {
        "type": "done",
        "id": profile["id"],
        "path": str(path),
        "profile_path": str(saved_path),
        "warnings": warnings,
        "profile": profile,
        "ts": utc_now(),
    }
    append_audit({"event": "done", "path": str(path), "id": profile["id"], "warnings": warnings})
    await broadcaster.broadcast(done)
    return profile


async def run_worker(queue: asyncio.Queue[Path], broadcaster: Broadcaster, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            path = await asyncio.wait_for(queue.get(), timeout=0.5)
        except asyncio.TimeoutError:
            continue

        try:
            await process_file(path, broadcaster)
        except Exception as exc:
            error = {"type": "error", "path": str(path), "filename": path.name, "error": str(exc), "ts": utc_now()}
            append_audit({"event": "error", "path": str(path), "error": str(exc)})
            await broadcaster.broadcast(error)
        finally:
            queue.task_done()
