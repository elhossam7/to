import httpx
import pytest

from backend.pipeline.ollama import _post_streaming
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
        result = await _post_streaming(client, {"model": "test"})

    assert result == {"personal": {"full_name": "Ada Lovelace"}}


@pytest.mark.asyncio
async def test_post_streaming_raises_ollama_stream_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ollama_url", "http://ollama.test/api/generate")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'{"error":"model crashed"}\n')

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError, match="model crashed"):
            await _post_streaming(client, {"model": "test"})
