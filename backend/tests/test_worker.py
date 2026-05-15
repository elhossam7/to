from pathlib import Path

import pytest

from backend.pipeline.jobs import ProcessingJob
from backend.pipeline.worker import _extract_profile_from_documents
from backend.settings import settings


@pytest.mark.asyncio
async def test_batch_extracts_each_file_separately_and_merges(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    first = tmp_path / "chrome.txt"
    second = tmp_path / "edge.txt"
    job = ProcessingJob(paths=[first, second], source="upload_batch", batch_id="batch-1")
    documents = [(first.name, ["name: Ada Lovelace"]), (second.name, ["email: ada@example.com"])]
    calls: list[str] = []

    async def fake_call_ollama(docs: list[tuple[str, list[str]]]) -> dict:
        calls.append(docs[0][0])
        if docs[0][0] == first.name:
            return {"personal": {"full_name": "Ada Lovelace"}}
        return {"contact": {"emails": [{"address": "ada@example.com"}]}}

    monkeypatch.setattr("backend.pipeline.worker.call_ollama", fake_call_ollama)

    profile, warnings = await _extract_profile_from_documents(job, documents, [line for _, lines in documents for line in lines])

    assert calls == [first.name, second.name]
    assert profile["id"] == "name-ada-lovelace"
    assert profile["personal"]["full_name"] == "Ada Lovelace"
    assert profile["contact"]["emails"] == [{"address": "ada@example.com", "primary": True}]
    assert warnings == []


@pytest.mark.asyncio
async def test_batch_continues_when_one_file_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    settings.ensure_dirs()

    first = tmp_path / "bad.txt"
    second = tmp_path / "good.txt"
    job = ProcessingJob(paths=[first, second], source="upload_batch", batch_id="batch-2")
    documents = [(first.name, ["bad input"]), (second.name, ["email: ada@example.com"])]

    async def fake_call_ollama(docs: list[tuple[str, list[str]]]) -> dict:
        if docs[0][0] == first.name:
            raise RuntimeError("timeout")
        return {"contact": {"emails": [{"address": "ada@example.com"}]}}

    monkeypatch.setattr("backend.pipeline.worker.call_ollama", fake_call_ollama)

    profile, warnings = await _extract_profile_from_documents(job, documents, [line for _, lines in documents for line in lines])

    assert profile["id"] == "email-ada-example.com"
    assert profile["contact"]["emails"] == [{"address": "ada@example.com", "primary": True}]
    assert "failed_file:bad.txt" in warnings
