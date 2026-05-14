from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .settings import settings


_audit_lock = threading.Lock()
_safe_name_re = re.compile(r"[^a-zA-Z0-9_.-]+")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_id(value: str) -> str:
    cleaned = _safe_name_re.sub("-", str(value).strip()).strip(".-")
    return cleaned or "unknown"


def save_profile(profile_id: str, data: Dict[str, Any]) -> Path:
    settings.ensure_dirs()
    target = settings.profiles_dir / f"{safe_id(profile_id)}.json"
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=settings.profiles_dir,
        prefix=f".{target.stem}.",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp.write(payload)
        tmp.write("\n")
        temp_name = tmp.name

    os.replace(temp_name, target)
    return target


def append_audit(entry: Dict[str, Any]) -> None:
    settings.ensure_dirs()
    line = {"ts": utc_now(), **entry}
    with _audit_lock:
        with settings.audit_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def load_profile(profile_id: str) -> Optional[Dict[str, Any]]:
    path = settings.profiles_dir / f"{safe_id(profile_id)}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_profiles(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    settings.ensure_dirs()
    files = sorted(settings.profiles_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    rows: List[Dict[str, Any]] = []
    for path in files[offset : offset + limit]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("_profile_path", str(path))
            data.setdefault("_updated_at", datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat())
            rows.append(data)
        except (OSError, json.JSONDecodeError) as exc:
            append_audit({"event": "profile_read_error", "path": str(path), "error": str(exc)})
    return rows


def recent_audit(limit: int = 100) -> Iterable[Dict[str, Any]]:
    if not settings.audit_log.exists():
        return []
    lines = settings.audit_log.read_text(encoding="utf-8").splitlines()[-limit:]
    parsed = []
    for line in lines:
        try:
            parsed.append(json.loads(line))
        except json.JSONDecodeError:
            parsed.append({"ts": utc_now(), "event": "audit_parse_error", "raw": line})
    return parsed
