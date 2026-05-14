from pathlib import Path

import pytest

from backend.pipeline.validator import validate_profile


def test_validate_profile_generates_missing_id(tmp_path: Path) -> None:
    path = tmp_path / "source.txt"
    profile, warnings = validate_profile({"name": "Ada Lovelace"}, path, ["Ada Lovelace"])

    assert profile["id"].startswith("file-")
    assert "missing_identity_generated" in warnings
    assert profile["_warnings"] == ["missing_identity_generated"]


def test_validate_profile_uses_stable_full_name_id(tmp_path: Path) -> None:
    profile, warnings = validate_profile(
        {"personal": {"full_name": "Dadang Prastiya"}, "contact": {"emails": [{"address": "one@example.com"}]}},
        tmp_path / "google-1.txt",
        ["Dadang Prastiya"],
    )

    assert profile["id"] == "name-dadang-prastiya"
    assert profile["_id_strategy"] == "full_name"
    assert warnings == []


def test_validate_profile_rejects_empty_envelope(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        validate_profile({"id": "abc"}, tmp_path / "source.txt", ["abc"])
