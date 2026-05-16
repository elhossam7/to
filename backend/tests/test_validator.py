from pathlib import Path

import pytest

from backend.pipeline.validator import validate_profile


def test_validate_profile_generates_missing_id(tmp_path: Path) -> None:
    path = tmp_path / "source.txt"
    profile, warnings = validate_profile({"personal": {"first_name": "Ada"}}, path, ["Ada Lovelace"])

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


def test_validate_profile_moves_country_out_of_street(tmp_path: Path) -> None:
    profile, warnings = validate_profile(
        {
            "personal": {"first_name": "Soufiane", "last_name": "Elkasmi"},
            "address": {"street": "maroc", "city": "tanger", "postal_code": "90080"},
            "contact": {"emails": [{"address": "sfyankasmi@gmail.com"}]},
        },
        tmp_path / "source.txt",
        ["Name: soufiane elkasmi", "City: tanger", "Country: maroc"],
    )

    assert profile["address"]["street"] is None
    assert profile["address"]["country"] == "Morocco"
    assert profile["address"]["country_code"] == "MA"
    assert "country_moved_from_address_street" in warnings


def test_validate_profile_normalizes_labeled_nationality(tmp_path: Path) -> None:
    profile, warnings = validate_profile(
        {"personal": {"first_name": "Soufiane"}, "contact": {"emails": [{"address": "sfyankasmi@gmail.com"}]}},
        tmp_path / "source.txt",
        ["nationality: maroc"],
    )

    assert profile["personal"]["nationality"] == "Moroccan"
    assert warnings == []


def test_validate_profile_repairs_stringified_address_blob(tmp_path: Path) -> None:
    profile, warnings = validate_profile(
        {
            "address": {
                "city": "Karachi",
                "street": "{'street': None, 'city': Karachi, 'region': None, 'postal_code': None, 'country': Pakistan, 'country_code': PK}",
            },
            "contact": {"emails": [{"address": "xesahxe@gmail.com"}]},
        },
        tmp_path / "source.txt",
        ["city: Karachi", "country: Pakistan"],
    )

    assert profile["address"]["street"] is None
    assert profile["address"]["city"] == "Karachi"
    assert profile["address"]["country"] == "Pakistan"
    assert profile["address"]["country_code"] == "PK"
    assert "address_blob_repaired" in warnings
