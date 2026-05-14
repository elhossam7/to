from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Tuple


def fallback_id(path: Path, lines: List[str]) -> str:
    digest = hashlib.sha256(("\n".join(lines) + str(path.name)).encode("utf-8")).hexdigest()[:12]
    return f"file-{digest}"


def validate_profile(data: Any, path: Path, lines: List[str]) -> Tuple[Dict[str, Any], List[str]]:
    if not isinstance(data, dict):
        raise ValueError("Ollama response must be a JSON object")

    warnings: List[str] = []
    profile = dict(data)
    supplied_id = profile.get("id")
    if not isinstance(supplied_id, (str, int)) or not str(supplied_id).strip():
        profile["id"] = fallback_id(path, lines)
        warnings.append("missing_id_generated")
    else:
        profile["id"] = str(supplied_id).strip()

    non_meta_fields = [key for key in profile.keys() if key not in {"id", "_source", "_warnings"}]
    if not non_meta_fields:
        raise ValueError("profile must include at least one data field besides id")

    if warnings:
        existing = profile.get("_warnings")
        if isinstance(existing, list):
            profile["_warnings"] = [*existing, *warnings]
        else:
            profile["_warnings"] = warnings

    return profile, warnings
