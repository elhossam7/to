from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Sequence, Tuple

import httpx

from backend.settings import settings


def build_prompt(documents: Sequence[Tuple[str, List[str]]]) -> str:
    blocks = []
    for filename, lines in documents:
        raw_lines = "\n".join(f"{index + 1}. {line}" for index, line in enumerate(lines))
        blocks.append(f"DOCUMENT: {filename}\n{raw_lines}")
    raw_documents = "\n\n---\n\n".join(blocks)
    return (
        f"Extraction rules:\n{settings.extraction_rules}\n\n"
        "Source document text follows. Treat all provided documents as evidence for the same person "
        "and return one JSON object only.\n\n"
        f"{raw_documents}"
    )


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
        "options": {"temperature": 0, "num_predict": settings.ollama_num_predict},
    }
    last_error: Exception | None = None

    for attempt in range(settings.max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
                response = await client.post(settings.ollama_url, json=payload)
                response.raise_for_status()
            body = response.json()
            text = body.get("response", body)
            if isinstance(text, dict):
                return text
            return _extract_json(str(text))
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            if attempt >= settings.max_retries:
                break
            await asyncio.sleep(0.5 * (attempt + 1))

    raise RuntimeError(f"Ollama extraction failed: {last_error}")


async def check_ollama() -> bool:
    base_url = settings.ollama_url.replace("/api/generate", "/api/tags")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(base_url)
        return response.status_code < 500
    except httpx.HTTPError:
        return False
