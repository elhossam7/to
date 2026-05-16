from __future__ import annotations

import asyncio
import json
import re
from typing import Any, AsyncIterator, Dict, List, Sequence, Tuple

import httpx

from backend.pipeline.schema import PROFILE_SCHEMA_PROMPT
from backend.settings import settings


_signal_re = re.compile(
    r"(@|phone|mobile|tel|email|mail|name|nom|nombre|birth|dob|born|address|street|city|country|"
    r"national|id|passport|document|linkedin|facebook|github|twitter|website|language|"
    r"\b\d{4}-\d{2}-\d{2}\b|\+\d{6,})",
    re.IGNORECASE,
)
_non_recoverable_http_statuses = {401, 403, 404, 429}
EXTRACTION_ENGINE_PROMPT = """You are a strict profile extraction engine for noisy browser/export text.

Your output contract:
- Return exactly one raw JSON object. No markdown, no prose, no comments, no code fences.
- Use exactly the schema keys provided below. Do not invent new top-level keys or nested user-data keys.
- Scalar fields must be a string, number, or null. Never put an object, array, dictionary dump, or JSON string inside a scalar field.
- List fields must be arrays. Use [] when empty.
- Use null only when the value cannot be determined from visible evidence or an unambiguous geographic/phone-code inference.
- Do not include placeholder text like unknown, N/A, none, null, not provided, or empty strings.

Evidence discipline:
- Extract values visible in the source text.
- You may normalize formatting when the meaning is unchanged: trim whitespace, normalize email casing, normalize country names, and normalize ISO country codes.
- You may infer country, country_code, and region from visible city, region, postal code, phone/calling code, or country code only when the mapping is unambiguous.
- Never infer private personal facts such as date_of_birth, age, nationality, national_id, or phone number unless they are visible or directly labeled.
- Nationality is not the same as address country. Only fill nationality when it is visible or explicitly labeled as nationality/nationalite.
- If multiple documents are present, treat them as evidence for the same person and merge complementary facts.
- If values conflict, prefer the most specific and clearly labeled value. If conflict cannot be resolved, keep the safer visible value and leave uncertain fields null.

Identity rules:
- full_name should be the person's real full name when visible. Do not use an email username as full_name unless it is clearly presented as a name.
- first_name and last_name should come from a visible name when possible. If only full_name is visible and it clearly has name parts, split conservatively.
- national_id should contain document ID / national ID / passport / identity-number values only, not phone numbers, postal codes, or account IDs.

Address and geography rules:
- street is only the street/address line. Never put a country, city, region, postal code, phone code, or a nested address object in street.
- city is the locality/city/town.
- region is the state/province/governorate/wilaya/department/administrative region.
- country is the normalized English country name, e.g. Morocco, Algeria, Zambia, Pakistan.
- country_code is ISO 3166-1 alpha-2, e.g. MA, DZ, ZM, PK. It is not a telephone calling code.
- If the source shows a telephone/calling code such as +260 or country_code 260, infer the country only if that calling code is unambiguous, and output ISO country_code, not 260.
- If city/region/postal data clearly identifies a country or administrative region, fill the normalized country/country_code/region.
- Examples: Lusaka + 10101 or calling code 260 implies Zambia / ZM and region Lusaka Province. El Eulma or Setif/Sétif/سطيف implies Algeria / DZ and region Setif Province. Karachi implies Pakistan / PK when it is clearly an address city.
- Do not move country names into street. If a line is just Maroc/Morocco/Algeria/Zambia/Pakistan, it belongs in country, not street.

Contact rules:
- Extract all visible emails. Deduplicate case-insensitively. The first visible email is primary unless the source labels another as primary.
- Extract all visible phone numbers. Preserve a leading + and visible country code. Do not convert IDs or postal codes into phones.
- Online profile fields should contain visible URLs or handles for the matching service only.

Language rules:
- Fill languages only when explicitly visible. Do not infer languages from country, name, or address.
- Proficiency must be one of native, professional, intermediate, beginner, or null.

Common mistakes to avoid:
- Do not stringify nested objects into scalar fields.
- Do not output malformed JSON.
- Do not put city, country, region, or postal code in street.
- Do not use phone calling codes as ISO country_code.
- Do not confuse nationality with residence/address country.
- Do not add extra keys outside the schema."""


class OllamaHTTPError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Ollama HTTP {status_code}: {detail}")


def is_non_recoverable_ollama_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, OllamaHTTPError) and current.status_code in _non_recoverable_http_statuses:
            return True
        current = current.__cause__
    return False


def compact_lines(lines: List[str]) -> List[str]:
    if len(lines) <= settings.prompt_max_lines_per_doc:
        return lines

    chosen: List[str] = []
    seen = set()

    def add(line: str) -> None:
        key = line.lower()
        if key not in seen and len(chosen) < settings.prompt_max_lines_per_doc:
            seen.add(key)
            chosen.append(line)

    for line in lines:
        if _signal_re.search(line):
            add(line)
    for line in lines[: settings.prompt_max_lines_per_doc]:
        add(line)

    return chosen


def build_prompt(documents: Sequence[Tuple[str, List[str]]]) -> str:
    blocks = []
    for filename, lines in documents:
        compacted = compact_lines(lines)
        raw_lines = "\n".join(f"{index + 1}. {line}" for index, line in enumerate(compacted))
        blocks.append(f"DOCUMENT: {filename}\n{raw_lines}")
    raw_documents = "\n\n---\n\n".join(blocks)
    raw_documents = raw_documents[: settings.prompt_max_chars]
    return (
        f"{EXTRACTION_ENGINE_PROMPT}\n\n"
        f"{PROFILE_SCHEMA_PROMPT}\n\n"
        f"Project extraction rules, applied only when they do not conflict with the schema:\n{settings.extraction_rules}\n\n"
        "Source document text:\n"
        f"{raw_documents}"
    )


def _error_summary(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return exc.__class__.__name__
    return str(exc) or exc.__class__.__name__


def _extract_json(text: str) -> Dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.removeprefix("json").strip()

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        parsed = json.loads(stripped[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("response JSON is not an object")
    return parsed


async def call_ollama(documents: Sequence[Tuple[str, List[str]]]) -> Dict[str, Any]:
    prompt = build_prompt(documents)
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": settings.ollama_stream,
        "format": "json",
        "options": {"temperature": 0, "num_predict": settings.ollama_num_predict, "num_ctx": settings.ollama_num_ctx},
    }
    last_error: Exception | None = None

    for attempt in range(settings.max_retries + 1):
        try:
            timeout = httpx.Timeout(connect=10.0, read=settings.ollama_timeout, write=30.0, pool=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                if settings.ollama_stream:
                    return await _post_streaming(client, payload)
                return await _post_non_streaming(client, payload)
        except (httpx.TimeoutException, httpx.HTTPError, json.JSONDecodeError, RuntimeError, ValueError) as exc:
            last_error = exc
            if is_non_recoverable_ollama_error(exc):
                raise RuntimeError(f"Ollama extraction failed: {_error_summary(exc)}") from exc
            if attempt >= settings.max_retries:
                break
            await asyncio.sleep(0.5 * (attempt + 1))

    raise RuntimeError(f"Ollama extraction failed: {_error_summary(last_error) if last_error else 'unknown error'}") from last_error


async def _post_non_streaming(client: httpx.AsyncClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    response = await client.post(settings.ollama_url, json=payload)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = response.text.strip()[:500] or response.reason_phrase
        raise OllamaHTTPError(response.status_code, detail) from exc

    body = response.json()
    text = body.get("response", body)
    if isinstance(text, dict):
        return text
    return _extract_json(str(text))


async def _post_streaming(client: httpx.AsyncClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    chunks: List[str] = []
    async with client.stream("POST", settings.ollama_url, json=payload) as response:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = await response.aread()
            text = detail.decode("utf-8", errors="replace").strip()[:500] or response.reason_phrase
            raise OllamaHTTPError(response.status_code, text) from exc

        async for body in _ollama_stream_events(response):
            if body.get("error"):
                raise RuntimeError(f"Ollama stream error: {body['error']}")
            fragment = body.get("response")
            if isinstance(fragment, str):
                chunks.append(fragment)
            elif isinstance(fragment, dict):
                return fragment

    if not chunks:
        raise ValueError("Ollama stream returned no response text")
    return _extract_json("".join(chunks))


async def _ollama_stream_events(response: httpx.Response) -> AsyncIterator[Dict[str, Any]]:
    async for line in response.aiter_lines():
        if not line.strip():
            continue
        event = json.loads(line)
        if not isinstance(event, dict):
            raise ValueError("Ollama stream event is not a JSON object")
        yield event


async def check_ollama() -> bool:
    base_url = settings.ollama_url.replace("/api/generate", "/api/tags")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(base_url)
        return response.status_code < 500
    except httpx.HTTPError:
        return False
