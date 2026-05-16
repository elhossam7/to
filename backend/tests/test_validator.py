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


def test_validate_profile_normalizes_zambia_calling_code_and_lusaka_region(tmp_path: Path) -> None:
    profile, warnings = validate_profile(
        {
            "personal": {"full_name": "Justin Sikwese", "national_id": "349192-16-1"},
            "address": {"city": "LUSAKA", "country": None, "country_code": "260", "postal_code": "10101"},
            "contact": {"emails": [{"address": "Kasondexyz@gmail.com"}]},
        },
        tmp_path / "source.txt",
        ["city: LUSAKA", "country code: 260", "postal code: 10101"],
    )

    assert profile["address"]["country"] == "Zambia"
    assert profile["address"]["country_code"] == "ZM"
    assert profile["address"]["region"] == "Lusaka Province"
    assert "country_code_normalized_from_calling_code" in warnings
    assert "region_inferred_from_location" in warnings


def test_validate_profile_infers_zambia_from_lusaka_city(tmp_path: Path) -> None:
    profile, warnings = validate_profile(
        {
            "personal": {"full_name": "Justin Sikwese"},
            "address": {"city": "LUSAKA", "postal_code": "10101"},
            "contact": {"emails": [{"address": "Kasondexyz@gmail.com"}]},
        },
        tmp_path / "source.txt",
        ["city: LUSAKA", "postal code: 10101"],
    )

    assert profile["address"]["country"] == "Zambia"
    assert profile["address"]["country_code"] == "ZM"
    assert profile["address"]["region"] == "Lusaka Province"
    assert "country_inferred_from_city" in warnings


def test_validate_profile_infers_algeria_from_arabic_setif_region(tmp_path: Path) -> None:
    profile, warnings = validate_profile(
        {
            "address": {
                "city": "EL EULMA",
                "country": None,
                "country_code": None,
                "region": "\u0633\u0637\u064a\u0641",
                "street": "\u0634\u0627\u0631\u0639 \u0628\u0644\u062e\u064a\u0631\u064a \u0645\u0631\u0648\u0627\u0646\u064a \u062d\u064a 36 \u0635\u062e\u0631\u064a",
            },
            "contact": {"emails": [{"address": "hadsaid77@gmail.com"}]},
        },
        tmp_path / "source.txt",
        ["city: EL EULMA", "region: \u0633\u0637\u064a\u0641"],
    )

    assert profile["address"]["country"] == "Algeria"
    assert profile["address"]["country_code"] == "DZ"
    assert profile["address"]["region"] == "Setif Province"
    assert "country_inferred_from_region" in warnings


def test_validate_profile_infers_algeria_from_el_eulma_city(tmp_path: Path) -> None:
    profile, warnings = validate_profile(
        {
            "address": {"city": "EL EULMA", "country": None, "country_code": None, "region": None},
            "contact": {"emails": [{"address": "hadsaid77@gmail.com"}]},
        },
        tmp_path / "source.txt",
        ["city: EL EULMA"],
    )

    assert profile["address"]["country"] == "Algeria"
    assert profile["address"]["country_code"] == "DZ"
    assert profile["address"]["region"] == "Setif Province"
    assert "country_inferred_from_city" in warnings


def test_validate_profile_infers_egyptian_nationality_from_egypt_address(tmp_path: Path) -> None:
    profile, warnings = validate_profile(
        {
            "personal": {
                "full_name": "Manar Asem Hussien",
                "date_of_birth": "2001-12-12",
                "place_of_birth": "Mansoura",
                "nationality": None,
            },
            "address": {"city": "Suez", "country": "Egypt", "country_code": "EG", "region": "Suez"},
            "contact": {"emails": [{"address": "kokoelkholy12@gmail.com"}]},
        },
        tmp_path / "source.txt",
        ["place of birth: Mansoura", "address: Suez, Egypt"],
    )

    assert profile["personal"]["nationality"] == "Egyptian"
    assert profile["address"]["country"] == "Egypt"
    assert profile["address"]["country_code"] == "EG"
    assert "nationality_inferred_from_place" in warnings


def test_validate_profile_infers_egypt_from_suez_city(tmp_path: Path) -> None:
    profile, warnings = validate_profile(
        {
            "personal": {"full_name": "Manar Asem Hussien", "nationality": None},
            "address": {"city": "Suez", "country": None, "country_code": None, "region": None},
            "contact": {"emails": [{"address": "kokoelkholy12@gmail.com"}]},
        },
        tmp_path / "source.txt",
        ["city: Suez"],
    )

    assert profile["address"]["country"] == "Egypt"
    assert profile["address"]["country_code"] == "EG"
    assert profile["address"]["region"] == "Suez Governorate"
    assert profile["personal"]["nationality"] == "Egyptian"
    assert "country_inferred_from_city" in warnings
