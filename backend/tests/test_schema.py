from backend.pipeline.schema import normalize_profile


def test_normalize_profile_drops_unknown_keys_and_maps_aliases() -> None:
    profile = normalize_profile(
        {
            "username": "manuel dario cardozo",
            "documentNumber": "23088910",
            "contactDetails": {"email": "cardozo1973@outlook.com", "phone": "2964 618875"},
            "frequentFlyerNumber": "38097366",
            "location": {"address": "cabo de hornos 652", "city": "rio grande", "province": "tierra del fuego", "zipCode": "9420"},
        }
    )

    assert set(profile) == {"personal", "address", "contact", "online_profiles", "languages"}
    assert profile["personal"]["full_name"] == "manuel dario cardozo"
    assert profile["personal"]["national_id"] == "23088910"
    assert profile["contact"]["emails"] == [{"address": "cardozo1973@outlook.com", "primary": True}]
    assert profile["contact"]["phones"] == [{"number": "2964 618875", "type": None, "primary": True}]
    assert profile["address"]["region"] == "tierra del fuego"
    assert "frequentFlyerNumber" not in profile
