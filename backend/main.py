from __future__ import annotations

import asyncio
import json
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from watchdog.observers import Observer

from backend.broadcaster import Broadcaster
from backend.pipeline.ollama import check_ollama
from backend.pipeline.worker import run_worker
from backend.settings import settings
from backend.storage import append_audit, list_profiles, load_profile, safe_id, utc_now
from backend.watcher import InboxHandler


class AppState:
    queue: asyncio.Queue[Path]
    broadcaster: Broadcaster
    stop_event: asyncio.Event
    worker_task: asyncio.Task[None]
    observer: Observer


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings.ensure_dirs()
    loop = asyncio.get_running_loop()
    state.queue = asyncio.Queue()
    state.broadcaster = Broadcaster()
    state.stop_event = asyncio.Event()
    state.worker_task = asyncio.create_task(run_worker(state.queue, state.broadcaster, state.stop_event))

    handler = InboxHandler(loop, state.queue)
    state.observer = Observer()
    state.observer.schedule(handler, str(settings.inbox_dir), recursive=False)
    state.observer.start()
    append_audit({"event": "startup", "data_dir": str(settings.data_dir)})

    try:
        yield
    finally:
        append_audit({"event": "shutdown"})
        state.stop_event.set()
        state.observer.stop()
        state.observer.join(timeout=5)
        state.worker_task.cancel()
        try:
            await state.worker_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/status")
async def status() -> dict:
    return {
        "queue_size": state.queue.qsize(),
        "worker_alive": not state.worker_task.done(),
        "ollama_reachable": await check_ollama(),
        "ollama_model": settings.ollama_model,
        "data_dir": str(settings.data_dir),
        "inbox_dir": str(settings.inbox_dir),
        "profiles_dir": str(settings.profiles_dir),
    }


@app.post("/ingest")
async def ingest(file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are accepted")

    settings.ensure_dirs()
    target_name = safe_id(Path(file.filename).stem) + ".txt"
    target = settings.inbox_dir / target_name
    temp_target = settings.inbox_dir / f".{target_name}.uploading"
    with temp_target.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    if temp_target.stat().st_size > settings.max_file_size:
        temp_target.unlink(missing_ok=True)
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_file_size} bytes")

    temp_target.replace(target)
    await state.queue.put(target)
    event = {"type": "queued", "path": str(target), "filename": target.name, "ts": utc_now()}
    append_audit({"event": "queued", "path": str(target), "source": "upload"})
    await state.broadcaster.broadcast(event)
    return {"accepted": True, "filename": target.name, "path": str(target)}


@app.get("/profiles")
async def profiles(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)) -> list[dict]:
    return list_profiles(limit=limit, offset=offset)


@app.get("/profiles/{profile_id}")
async def profile(profile_id: str) -> dict:
    data = load_profile(profile_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return data


@app.get("/events")
async def events() -> StreamingResponse:
    async def stream() -> AsyncIterator[str]:
        async with state.broadcaster.subscribe() as queue:
            yield f"data: {json.dumps({'type': 'connected', 'ts': utc_now()})}\n\n"
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/")
async def root() -> dict:
    return {"name": settings.app_name, "status": "ok"}
