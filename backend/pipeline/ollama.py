from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Sequence, Tuple

import httpx

from backend.pipeline.schema import PROFILE_SCHEMA_PROMPT
from backend.settings import settings


_signal_re = re.compile(
    r"(@|phone|mobile|tel|email|mail|name|nom|nombre|birth|dob|born|address|street|city|country|"
    r"national|id|passport|document|linkedin|facebook|github|twitter|website|language|"
    r"\b\d{4}-\d{2}-\d{2}\b|\+\d{6,})",
    re.IGNORECASE,
)


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
        "You are a precise document extraction engine. Return exactly one raw JSON object and nothing else. "
        "Use only values visible in the source text; do not guess. Never add keys outside the schema. "
        "Use null for missing scalar fields and [] for missing list fields. Treat all source documents as "
        "evidence for the same person.\n\n"
        f"{PROFILE_SCHEMA_PROMPT}\n\n"
        f"Project extraction rules, applied only when they do not conflict with the schema:\n{settings.extraction_rules}\n\n"
        "Source document text:\n"
        f"{raw_documents}"
    )


def _error_summary(exc: Exception) -> str:
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
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "num_predict": settings.ollama_num_predict, "num_ctx": settings.ollama_num_ctx},
    }
    last_error: Exception | None = None

    for attempt in range(settings.max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
                response = await client.post(settings.ollama_url, json=payload)
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    detail = response.text.strip()[:500] or response.reason_phrase
                    raise RuntimeError(f"Ollama HTTP {response.status_code}: {detail}") from exc
            body = response.json()
            text = body.get("response", body)
            if isinstance(text, dict):
                return text
            return _extract_json(str(text))
        except (httpx.TimeoutException, httpx.HTTPError, json.JSONDecodeError, RuntimeError, ValueError) as exc:
            last_error = exc
            if attempt >= settings.max_retries:
                break
            await asyncio.sleep(0.5 * (attempt + 1))

    raise RuntimeError(f"Ollama extraction failed: {_error_summary(last_error) if last_error else 'unknown error'}")


async def check_ollama() -> bool:
    base_url = settings.ollama_url.replace("/api/generate", "/api/tags")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(base_url)
        return response.status_code < 500
    except httpx.HTTPError:
        return False
