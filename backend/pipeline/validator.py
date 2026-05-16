from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from backend.pipeline.schema import has_visible_data, normalize_profile


_safe_name_re = re.compile(r"[^a-zA-Z0-9_.-]+")
_label_value_re = re.compile(r"\b(?P<label>nationality|nationalite|nationalit[eé]|country|pays)\b\s*[:=-]?\s*(?P<value>.+)", re.IGNORECASE)
_country_aliases = {
    "ma": ("Morocco", "MA"),
    "maroc": ("Morocco", "MA"),
    "morroco": ("Morocco", "MA"),
    "morocco": ("Morocco", "MA"),
    "marruecos": ("Morocco", "MA"),
    "pk": ("Pakistan", "PK"),
    "pakistan": ("Pakistan", "PK"),
}
_country_codes = {"MA": "Morocco", "PK": "Pakistan"}
_nationality_aliases = {
    "maroc": "Moroccan",
    "marocain": "Moroccan",
    "marocaine": "Moroccan",
    "moroccan": "Moroccan",
    "pakistan": "Pakistani",
    "pakistani": "Pakistani",
}


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


def _alias_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def _country_alias(value: Any) -> Tuple[str, str] | None:
    key = _alias_key(value)
    return _country_aliases.get(key)


def _nationality_alias(value: Any) -> str | None:
    key = _alias_key(value)
    return _nationality_aliases.get(key)


def _line_labeled_value(lines: List[str], labels: set[str]) -> str | None:
    for line in lines:
        match = _label_value_re.search(line)
        if not match:
            continue
        label = _alias_key(match.group("label"))
        if label in labels:
            return match.group("value").strip()
    return None


def _blob_value(text: Any, field: str) -> str | None:
    if not isinstance(text, str) or "{" not in text or field not in text:
        return None
    match = re.search(rf"['\"]?{re.escape(field)}['\"]?\s*:\s*['\"]?(?P<value>[^,'\"}}]+)", text)
    if not match:
        return None
    value = match.group("value").strip()
    if _alias_key(value) in {"none", "null"}:
        return None
    return value


def _repair_address_blob(address: Dict[str, Any]) -> bool:
    for source_field in ("street", "city", "region", "postal_code", "country", "country_code"):
        blob = address.get(source_field)
        if not isinstance(blob, str) or "{" not in blob:
            continue
        repaired = False
        for target_field in ("street", "city", "region", "postal_code", "country", "country_code"):
            value = _blob_value(blob, target_field)
            if value and (not address.get(target_field) or address.get(target_field) == blob):
                address[target_field] = value
                repaired = True
        if repaired and address.get(source_field) == blob:
            address[source_field] = None
        return repaired
    return False


def repair_profile(profile: Dict[str, Any], lines: List[str]) -> List[str]:
    warnings: List[str] = []
    address = profile["address"]
    personal = profile["personal"]

    if _repair_address_blob(address):
        warnings.append("address_blob_repaired")

    country = _country_alias(address.get("country"))
    if country:
        address["country"], address["country_code"] = country
    elif isinstance(address.get("country_code"), str):
        code = address["country_code"].strip().upper()
        if code in _country_codes:
            address["country"] = address.get("country") or _country_codes[code]
            address["country_code"] = code

    if not address.get("country"):
        labeled_country = _line_labeled_value(lines, {"country", "pays"})
        country = _country_alias(labeled_country) if labeled_country else None
        if country:
            address["country"], address["country_code"] = country

    for field in ("street", "city", "region"):
        country = _country_alias(address.get(field))
        if not country:
            continue
        if not address.get("country"):
            address["country"], address["country_code"] = country
        elif not address.get("country_code"):
            address["country_code"] = country[1]
        address[field] = None
        warnings.append(f"country_moved_from_address_{field}")

    nationality = _nationality_alias(personal.get("nationality"))
    if nationality:
        personal["nationality"] = nationality
    elif not personal.get("nationality"):
        labeled_nationality = _line_labeled_value(lines, {"nationality", "nationalite"})
        nationality = _nationality_alias(labeled_nationality) if labeled_nationality else None
        if nationality:
            personal["nationality"] = nationality

    return warnings


def validate_profile(data: Any, path: Path, lines: List[str]) -> Tuple[Dict[str, Any], List[str]]:
    if not isinstance(data, dict):
        raise ValueError("Ollama response must be a JSON object")

    warnings: List[str] = []
    supplied_id = data.get("id")
    profile = normalize_profile(data)
    warnings.extend(repair_profile(profile, lines))
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
