import httpx
import pytest

from backend.pipeline.ollama import OllamaHTTPError, call_ollama, is_non_recoverable_ollama_error
from backend.settings import settings


@pytest.mark.asyncio
async def test_post_streaming_joins_ollama_response_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ollama_url", "http://ollama.test/api/generate")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://ollama.test/api/generate"
        content = (
            b'{"response":"{\\"personal\\":{\\"full_name\\":\\"Ada","done":false}\n'
            b'{"response":" Lovelace\\"}}","done":true}\n'
        )
        return httpx.Response(200, content=content)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        from backend.pipeline.ollama import _post_streaming

        result = await _post_streaming(client, {"model": "test"})

    assert result == {"personal": {"full_name": "Ada Lovelace"}}


@pytest.mark.asyncio
async def test_post_streaming_raises_ollama_stream_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ollama_url", "http://ollama.test/api/generate")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'{"error":"model crashed"}\n')

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        from backend.pipeline.ollama import _post_streaming

        with pytest.raises(RuntimeError, match="model crashed"):
            await _post_streaming(client, {"model": "test"})


@pytest.mark.asyncio
async def test_call_ollama_does_not_retry_usage_limit_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ollama_url", "http://ollama.test/api/generate")
    monkeypatch.setattr(settings, "ollama_stream", True)
    monkeypatch.setattr(settings, "max_retries", 2)
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, content=b'{"error":"usage limit"}')

    original_client = httpx.AsyncClient

    def client_factory(*args: object, **kwargs: object) -> httpx.AsyncClient:
        timeout = kwargs.get("timeout")
        return original_client(transport=httpx.MockTransport(handler), timeout=timeout)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    with pytest.raises(RuntimeError) as exc_info:
        await call_ollama([("source.txt", ["email: ada@example.com"])])

    assert calls == 1
    assert is_non_recoverable_ollama_error(exc_info.value)


def test_ollama_http_429_is_non_recoverable() -> None:
    assert is_non_recoverable_ollama_error(OllamaHTTPError(429, "usage limit"))
