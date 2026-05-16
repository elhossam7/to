from __future__ import annotations

import asyncio
import ast
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
EXTRACTION_ENGINE_PROMPT = """You extract one person profile from noisy browser/export text.

Output exactly one raw JSON object: no markdown, no prose, no code fences. Use only the schema keys. Scalars must be string/number/null; never put objects, arrays, dictionary dumps, or JSON strings inside scalar fields. Lists must be arrays. No placeholders such as unknown, N/A, none, null, or empty strings.

Evidence and merge rules: use visible source values, plus only unambiguous geography/phone-code inference. Treat all documents as the same person and merge complementary facts. Resolve conflicts by preferring clearly labeled, specific values; otherwise leave uncertain fields null.

Identity rules: full_name is the real person name when visible, not an email username unless clearly used as a name. Split first/last name only when obvious. national_id is only ID/passport/national-document data, not phone, postal, or account IDs.

Address/geography rules: street is only the street/address line. Never put country, city, region, postal code, phone code, or nested address objects in street. city is locality/town. region is state/province/governorate/wilaya. country is normalized English country name. country_code is ISO 3166-1 alpha-2, not a calling code. Infer country/country_code/region from city, region, postal code, phone/calling code, country code, or nationality when unambiguous. If nationality is blank and a country/place-of-birth/address signal clearly identifies the person's country, fill the matching nationality unless there is conflicting evidence. Apply this rule globally, not only to the examples below.

Examples: +260 or country_code 260 -> Zambia/ZM/Zambian; +20/Suez/Mansoura -> Egypt/EG/Egyptian; El Eulma or Setif/Arabic Setif -> Setif Province, Algeria/DZ/Algerian; Karachi -> Pakistan/PK/Pakistani; Paris -> France/FR/French; London -> United Kingdom/GB/British; Maroc/Morocco belongs in country, not street.

Contact/language rules: extract all visible emails and phones; deduplicate emails case-insensitively; first visible email is primary unless another is labeled primary. Preserve visible + phone codes. Do not turn IDs/postal codes into phones. Online profiles require visible matching URLs/handles. Languages only when explicit."""


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

    start = stripped.find("{")
    end = stripped.rfind("}")
    candidates = [stripped]
    if start != -1 and end > start:
        candidates.append(stripped[start : end + 1])

    last_error: Exception | None = None
    for candidate in candidates:
        for repaired in (candidate, _repair_json_text(candidate)):
            try:
                parsed = json.loads(repaired, strict=False)
            except json.JSONDecodeError as exc:
                last_error = exc
                continue
            if not isinstance(parsed, dict):
                raise ValueError("response JSON is not an object")
            return parsed

    for candidate in candidates:
        try:
            parsed = ast.literal_eval(candidate)
        except (SyntaxError, ValueError) as exc:
            last_error = exc
            continue
        if not isinstance(parsed, dict):
            raise ValueError("response JSON is not an object")
        return parsed

    if last_error:
        raise last_error
    raise ValueError("response JSON is not an object")


def _repair_json_text(text: str) -> str:
    repaired = text.strip()
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    repaired = re.sub(
        r'(?P<value>"(?:[^"\\]|\\.)*"|[}\]]|-?\d+(?:\.\d+)?|true|false|null)\s+(?="[^"\n\r]+?"\s*:)',
        r"\g<value>, ",
        repaired,
        flags=re.IGNORECASE,
    )
    return repaired


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
