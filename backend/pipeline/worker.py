from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List

from backend.broadcaster import Broadcaster
from backend.pipeline.ollama import call_ollama
from backend.pipeline.parser import read_lines
from backend.pipeline.jobs import ProcessingJob
from backend.pipeline.schema import normalize_profile
from backend.pipeline.validator import validate_profile
from backend.storage import append_audit, load_profile, save_profile, utc_now


def source_meta(path: Path) -> Dict[str, Any]:
    try:
        stat = path.stat()
        size = stat.st_size
    except OSError:
        size = None
    return {"filename": path.name, "path": str(path), "size": size}


def _merge_value(old: Any, new: Any) -> Any:
    if new is None:
        return old
    if old is None:
        return new
    if isinstance(old, dict) and isinstance(new, dict):
        return {key: _merge_value(old.get(key), new.get(key)) for key in old.keys() | new.keys()}
    if isinstance(old, list) and isinstance(new, list):
        merged = list(old)
        seen = {repr(item) for item in merged}
        for item in new:
            marker = repr(item)
            if marker not in seen:
                merged.append(item)
                seen.add(marker)
        return merged
    return new


def _merge_profile(existing: Dict[str, Any] | None, profile: Dict[str, Any]) -> Dict[str, Any]:
    if existing is None:
        return profile
    existing_schema = normalize_profile(existing)
    merged = _merge_value(existing_schema, profile)
    if isinstance(merged, dict):
        merged["id"] = profile["id"]
        merged["_id_strategy"] = profile.get("_id_strategy", existing.get("_id_strategy"))
    return merged


async def process_job(job: ProcessingJob, broadcaster: Broadcaster) -> Dict[str, Any]:
    await broadcaster.broadcast(
        {
            "type": "started",
            "path": str(job.paths[0]) if job.paths else None,
            "filename": job.label,
            "filenames": [path.name for path in job.paths],
            "batch_id": job.batch_id,
            "ts": utc_now(),
        }
    )
    append_audit({"event": "started", "batch_id": job.batch_id, "paths": [str(path) for path in job.paths]})

    documents: List[tuple[str, List[str]]] = []
    all_lines: List[str] = []
    for path in job.paths:
        lines = read_lines(path)
        documents.append((path.name, lines))
        all_lines.extend(lines)

    result = await call_ollama(documents)
    primary_path = job.paths[0]
    profile, warnings = validate_profile(result, primary_path, all_lines)
    profile["_source"] = {
        "batch_id": job.batch_id,
        "source": job.source,
        "files": [source_meta(path) for path in job.paths],
        "filename": job.label,
        "processed_at": utc_now(),
        "line_count": len(all_lines),
    }

    existing = load_profile(profile["id"])
    profile = _merge_profile(existing, profile)
    saved_path = save_profile(profile["id"], profile)

    done = {
        "type": "done",
        "id": profile["id"],
        "path": str(primary_path),
        "filename": job.label,
        "filenames": [path.name for path in job.paths],
        "batch_id": job.batch_id,
        "profile_path": str(saved_path),
        "warnings": warnings,
        "profile": profile,
        "ts": utc_now(),
    }
    append_audit(
        {
            "event": "done",
            "batch_id": job.batch_id,
            "paths": [str(path) for path in job.paths],
            "id": profile["id"],
            "warnings": warnings,
        }
    )
    await broadcaster.broadcast(done)
    return profile


async def run_worker(queue: asyncio.Queue[ProcessingJob], broadcaster: Broadcaster, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            job = await asyncio.wait_for(queue.get(), timeout=0.5)
        except asyncio.TimeoutError:
            continue

        try:
            await process_job(job, broadcaster)
        except Exception as exc:
            error = {
                "type": "error",
                "path": str(job.paths[0]) if job.paths else None,
                "filename": job.label,
                "filenames": [path.name for path in job.paths],
                "batch_id": job.batch_id,
                "error": str(exc),
                "ts": utc_now(),
            }
            append_audit({"event": "error", "batch_id": job.batch_id, "paths": [str(path) for path in job.paths], "error": str(exc)})
            await broadcaster.broadcast(error)
        finally:
            queue.task_done()
