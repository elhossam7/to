from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from backend.pipeline.schema import has_visible_data, normalize_profile


_safe_name_re = re.compile(r"[^a-zA-Z0-9_.-]+")


def fallback_id(path: Path, lines: List[str]) -> str:
    digest = hashlib.sha256(("\n".join(lines) + str(path.name)).encode("utf-8")).hexdigest()[:12]
    return f"file-{digest}"


def _value_at(data: Dict[str, Any], path: Iterable[str]) -> str | None:
    current: Any = data
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    if isinstance(current, str) and current.strip():
        return current.strip()
    return None


def _first_array_value(data: Dict[str, Any], path: Iterable[str], field: str) -> str | None:
    current: Any = data
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    if not isinstance(current, list):
        return None
    for item in current:
        if isinstance(item, dict) and isinstance(item.get(field), str) and item[field].strip():
            return item[field].strip()
    return None


def stable_profile_id(data: Dict[str, Any], path: Path, lines: List[str]) -> Tuple[str, str]:
    national_id = _value_at(data, ("personal", "national_id"))
    if national_id:
        return _slug(f"nid-{national_id}"), "national_id"

    full_name = _value_at(data, ("personal", "full_name"))
    date_of_birth = _value_at(data, ("personal", "date_of_birth"))
    if full_name and date_of_birth:
        return _slug(f"name-dob-{full_name}-{date_of_birth}"), "full_name_date_of_birth"
    if full_name:
        return _slug(f"name-{full_name}"), "full_name"

    email = _first_array_value(data, ("contact", "emails"), "address")
    if email:
        return _slug(f"email-{email.lower()}"), "email"

    phone = _first_array_value(data, ("contact", "phones"), "number")
    if phone:
        return _slug(f"phone-{phone}"), "phone"

    return fallback_id(path, lines), "fallback"


def _slug(value: str) -> str:
    cleaned = _safe_name_re.sub("-", value.strip().lower()).strip(".-")
    return cleaned or "unknown"


def validate_profile(data: Any, path: Path, lines: List[str]) -> Tuple[Dict[str, Any], List[str]]:
    if not isinstance(data, dict):
        raise ValueError("Ollama response must be a JSON object")

    warnings: List[str] = []
    supplied_id = data.get("id")
    profile = normalize_profile(data)
    if isinstance(supplied_id, (str, int)) and str(supplied_id).strip():
        profile["id"] = str(supplied_id).strip()
        profile["_id_strategy"] = "model_id"
    else:
        profile_id, strategy = stable_profile_id(profile, path, lines)
        profile["id"] = profile_id
        profile["_id_strategy"] = strategy
        if strategy == "fallback":
            warnings.append("missing_identity_generated")

    if not has_visible_data({key: value for key, value in profile.items() if not key.startswith("_") and key != "id"}):
        raise ValueError("profile must include at least one data field besides id")

    if warnings:
        existing = profile.get("_warnings")
        if isinstance(existing, list):
            profile["_warnings"] = [*existing, *warnings]
        else:
            profile["_warnings"] = warnings

    return profile, warnings
