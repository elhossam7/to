from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, Iterable, List


PROFILE_SCHEMA_PROMPT = """Return exactly this JSON object shape. Do not add any other user-data keys:
{"personal":{"first_name":null,"last_name":null,"full_name":null,"date_of_birth":null,"age":null,"place_of_birth":null,"nationality":null,"national_id":null},"address":{"street":null,"city":null,"region":null,"postal_code":null,"country":null,"country_code":null},"contact":{"phones":[],"emails":[]},"online_profiles":{"linkedin":null,"facebook":null,"github":null,"twitter":null,"website":null},"languages":[]}"""

EMPTY_PROFILE: Dict[str, Any] = {
    "personal": {
        "first_name": None,
        "last_name": None,
        "full_name": None,
        "date_of_birth": None,
        "age": None,
        "place_of_birth": None,
        "nationality": None,
        "national_id": None,
    },
    "address": {
        "street": None,
        "city": None,
        "region": None,
        "postal_code": None,
        "country": None,
        "country_code": None,
    },
    "contact": {
        "phones": [],
        "emails": [],
    },
    "online_profiles": {
        "linkedin": None,
        "facebook": None,
        "github": None,
        "twitter": None,
        "website": None,
    },
    "languages": [],
}


def empty_profile() -> Dict[str, Any]:
    return deepcopy(EMPTY_PROFILE)


def normalize_profile(data: Dict[str, Any]) -> Dict[str, Any]:
    profile = empty_profile()

    personal = _dict(data.get("personal"))
    profile["personal"]["first_name"] = _first_text([personal, data], ["first_name", "firstName", "given_name", "givenName"])
    profile["personal"]["last_name"] = _first_text([personal, data], ["last_name", "lastName", "surname", "family_name", "familyName"])
    profile["personal"]["full_name"] = _first_text([personal, data], ["full_name", "fullName", "name", "username"])
    profile["personal"]["date_of_birth"] = _first_text([personal, data], ["date_of_birth", "dateOfBirth", "birth_date", "birthDate", "dob"])
    profile["personal"]["age"] = _first_int([personal, data], ["age"])
    profile["personal"]["place_of_birth"] = _first_text([personal, data], ["place_of_birth", "placeOfBirth", "birth_place", "birthPlace"])
    profile["personal"]["nationality"] = _first_text([personal, data], ["nationality"])
    profile["personal"]["national_id"] = _first_text(
        [personal, data],
        ["national_id", "nationalId", "nationalID", "id_number", "idNumber", "document_number", "documentNumber"],
    )

    address = _dict(data.get("address")) or _dict(data.get("location"))
    profile["address"]["street"] = _first_text([address, data], ["street", "street_address", "streetAddress", "address"])
    profile["address"]["city"] = _first_text([address, data], ["city", "town"])
    profile["address"]["region"] = _first_text([address, data], ["region", "province", "state"])
    profile["address"]["postal_code"] = _first_text([address, data], ["postal_code", "postalCode", "zip", "zipCode"])
    profile["address"]["country"] = _first_text([address, data], ["country"])
    profile["address"]["country_code"] = _first_text([address, data], ["country_code", "countryCode"])
    if isinstance(data.get("location"), str) and not profile["address"]["city"]:
        profile["address"]["city"] = _clean_text(data["location"])

    contact = _dict(data.get("contact")) or _dict(data.get("contact_details")) or _dict(data.get("contactDetails"))
    profile["contact"]["phones"] = _normalize_phones(
        _first_present([contact, data], ["phones", "phone_numbers", "phoneNumbers", "phone", "mobile"])
    )
    profile["contact"]["emails"] = _normalize_emails(_first_present([contact, data], ["emails", "email_addresses", "emailAddresses", "email"]))

    online = _dict(data.get("online_profiles")) or _dict(data.get("onlineProfiles")) or {}
    for key in profile["online_profiles"].keys():
        profile["online_profiles"][key] = _first_text([online, data], [key])

    profile["languages"] = _normalize_languages(data.get("languages"))
    return profile


def has_visible_data(profile: Dict[str, Any]) -> bool:
    def walk(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return True
        if isinstance(value, (str, int, float)):
            return bool(str(value).strip())
        if isinstance(value, list):
            return any(walk(item) for item in value)
        if isinstance(value, dict):
            return any(walk(item) for item in value.values())
        return False

    return walk(profile)


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_present(sources: Iterable[Dict[str, Any]], keys: Iterable[str]) -> Any:
    for source in sources:
        for key in keys:
            if key in source and source[key] not in (None, ""):
                return source[key]
    return None


def _first_text(sources: Iterable[Dict[str, Any]], keys: Iterable[str]) -> str | None:
    for source in sources:
        for key in keys:
            if key not in source or source[key] in (None, ""):
                continue
            text = _clean_text(source[key])
            if text:
                return text
    return None


def _first_int(sources: Iterable[Dict[str, Any]], keys: Iterable[str]) -> int | None:
    value = _first_present(sources, keys)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list, tuple, set)):
        return None
    text = str(value).strip()
    return text or None


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_phones(value: Any) -> List[Dict[str, Any]]:
    phones = []
    seen = set()
    for index, item in enumerate(_as_list(value)):
        if isinstance(item, dict):
            number = _clean_text(item.get("number") or item.get("phone"))
            phone_type = _clean_text(item.get("type"))
            primary = bool(item.get("primary")) if "primary" in item else index == 0
        else:
            number = _clean_text(item)
            phone_type = None
            primary = index == 0
        if not number or number in seen:
            continue
        seen.add(number)
        if phone_type not in {"mobile", "home", "work", "secondary"}:
            phone_type = None
        phones.append({"number": number, "type": phone_type, "primary": primary})
    return _single_primary(phones)


def _normalize_emails(value: Any) -> List[Dict[str, Any]]:
    emails = []
    seen = set()
    for index, item in enumerate(_as_list(value)):
        address = _clean_text(item.get("address") if isinstance(item, dict) else item)
        if not address:
            continue
        matches = re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", address)
        address = matches[0] if matches else address
        lowered = address.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        primary = bool(item.get("primary")) if isinstance(item, dict) and "primary" in item else index == 0
        emails.append({"address": address, "primary": primary})
    return _single_primary(emails)


def _normalize_languages(value: Any) -> List[Dict[str, Any]]:
    allowed = {"native", "professional", "intermediate", "beginner"}
    languages = []
    seen = set()
    for item in _as_list(value):
        if isinstance(item, dict):
            language = _clean_text(item.get("language"))
            proficiency = _clean_text(item.get("proficiency"))
            self_declared = bool(item.get("self_declared", item.get("selfDeclared", False)))
        else:
            language = _clean_text(item)
            proficiency = None
            self_declared = False
        if not language or language.lower() in seen:
            continue
        seen.add(language.lower())
        languages.append(
            {
                "language": language,
                "proficiency": proficiency if proficiency in allowed else None,
                "self_declared": self_declared,
            }
        )
    return languages


def _single_primary(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for index, item in enumerate(items):
        item["primary"] = index == 0
    return items
