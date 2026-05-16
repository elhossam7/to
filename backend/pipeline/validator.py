from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from backend.pipeline.schema import has_visible_data, normalize_profile


_safe_name_re = re.compile(r"[^a-zA-Z0-9_.-]+")
_label_value_re = re.compile(r"\b(?P<label>nationality|nationalite|nationalit[eé]|country|pays)\b\s*[:=-]?\s*(?P<value>.+)", re.IGNORECASE)
_country_rows = (
    ("AF", "Afghanistan", "Afghan", ("afghanistan",)),
    ("AL", "Albania", "Albanian", ("albania",)),
    ("DZ", "Algeria", "Algerian", ("algeria", "algerie", "algerien", "algerienne")),
    ("AR", "Argentina", "Argentine", ("argentina",)),
    ("AU", "Australia", "Australian", ("australia",)),
    ("AT", "Austria", "Austrian", ("austria",)),
    ("BD", "Bangladesh", "Bangladeshi", ("bangladesh",)),
    ("BE", "Belgium", "Belgian", ("belgium", "belgique")),
    ("BR", "Brazil", "Brazilian", ("brazil", "brasil")),
    ("BG", "Bulgaria", "Bulgarian", ("bulgaria",)),
    ("CA", "Canada", "Canadian", ("canada",)),
    ("CL", "Chile", "Chilean", ("chile",)),
    ("CN", "China", "Chinese", ("china", "prc")),
    ("CO", "Colombia", "Colombian", ("colombia",)),
    ("HR", "Croatia", "Croatian", ("croatia",)),
    ("CZ", "Czechia", "Czech", ("czechia", "czech republic")),
    ("DK", "Denmark", "Danish", ("denmark",)),
    ("EG", "Egypt", "Egyptian", ("egypt", "egypte", "misr")),
    ("FI", "Finland", "Finnish", ("finland",)),
    ("FR", "France", "French", ("france",)),
    ("DE", "Germany", "German", ("germany", "deutschland", "allemagne")),
    ("GH", "Ghana", "Ghanaian", ("ghana",)),
    ("GR", "Greece", "Greek", ("greece",)),
    ("HK", "Hong Kong", "Hong Konger", ("hong kong",)),
    ("HU", "Hungary", "Hungarian", ("hungary",)),
    ("IN", "India", "Indian", ("india",)),
    ("ID", "Indonesia", "Indonesian", ("indonesia",)),
    ("IR", "Iran", "Iranian", ("iran",)),
    ("IQ", "Iraq", "Iraqi", ("iraq",)),
    ("IE", "Ireland", "Irish", ("ireland",)),
    ("IT", "Italy", "Italian", ("italy", "italia")),
    ("JP", "Japan", "Japanese", ("japan",)),
    ("JO", "Jordan", "Jordanian", ("jordan",)),
    ("KE", "Kenya", "Kenyan", ("kenya",)),
    ("KW", "Kuwait", "Kuwaiti", ("kuwait",)),
    ("LB", "Lebanon", "Lebanese", ("lebanon", "liban")),
    ("LY", "Libya", "Libyan", ("libya",)),
    ("MY", "Malaysia", "Malaysian", ("malaysia",)),
    ("MX", "Mexico", "Mexican", ("mexico",)),
    ("MA", "Morocco", "Moroccan", ("morocco", "maroc", "morroco", "marruecos")),
    ("NL", "Netherlands", "Dutch", ("netherlands", "holland")),
    ("NZ", "New Zealand", "New Zealander", ("new zealand",)),
    ("NG", "Nigeria", "Nigerian", ("nigeria",)),
    ("NO", "Norway", "Norwegian", ("norway",)),
    ("OM", "Oman", "Omani", ("oman",)),
    ("PK", "Pakistan", "Pakistani", ("pakistan",)),
    ("PE", "Peru", "Peruvian", ("peru",)),
    ("PH", "Philippines", "Filipino", ("philippines",)),
    ("PL", "Poland", "Polish", ("poland",)),
    ("PT", "Portugal", "Portuguese", ("portugal",)),
    ("QA", "Qatar", "Qatari", ("qatar",)),
    ("RO", "Romania", "Romanian", ("romania",)),
    ("RU", "Russia", "Russian", ("russia", "russian federation")),
    ("SA", "Saudi Arabia", "Saudi", ("saudi arabia", "ksa")),
    ("RS", "Serbia", "Serbian", ("serbia",)),
    ("SG", "Singapore", "Singaporean", ("singapore",)),
    ("ZA", "South Africa", "South African", ("south africa",)),
    ("KR", "South Korea", "South Korean", ("south korea", "korea")),
    ("ES", "Spain", "Spanish", ("spain", "espana", "espagne")),
    ("SE", "Sweden", "Swedish", ("sweden",)),
    ("CH", "Switzerland", "Swiss", ("switzerland", "suisse")),
    ("SY", "Syria", "Syrian", ("syria",)),
    ("TH", "Thailand", "Thai", ("thailand",)),
    ("TN", "Tunisia", "Tunisian", ("tunisia", "tunisie")),
    ("TR", "Turkey", "Turkish", ("turkey", "turkiye")),
    ("UA", "Ukraine", "Ukrainian", ("ukraine",)),
    ("AE", "United Arab Emirates", "Emirati", ("united arab emirates", "uae", "emirates")),
    ("GB", "United Kingdom", "British", ("united kingdom", "uk", "great britain", "england")),
    ("US", "United States", "American", ("united states", "usa", "us", "america")),
    ("VE", "Venezuela", "Venezuelan", ("venezuela",)),
    ("VN", "Vietnam", "Vietnamese", ("vietnam",)),
    ("ZM", "Zambia", "Zambian", ("zambia",)),
)
_country_codes = {code: country for code, country, _nationality, _aliases in _country_rows}
_country_nationalities = {code: nationality for code, _country, nationality, _aliases in _country_rows}
_country_aliases = {
    alias: (country, code)
    for code, country, _nationality, aliases in _country_rows
    for alias in (code.lower(), country.lower(), *aliases)
}
_nationality_aliases = {
    alias: nationality
    for code, country, nationality, aliases in _country_rows
    for alias in (country.lower(), nationality.lower(), *aliases)
}
_calling_country_codes = {
    "20": ("Egypt", "EG"),
    "212": ("Morocco", "MA"),
    "213": ("Algeria", "DZ"),
    "216": ("Tunisia", "TN"),
    "218": ("Libya", "LY"),
    "260": ("Zambia", "ZM"),
    "27": ("South Africa", "ZA"),
    "30": ("Greece", "GR"),
    "31": ("Netherlands", "NL"),
    "33": ("France", "FR"),
    "34": ("Spain", "ES"),
    "39": ("Italy", "IT"),
    "41": ("Switzerland", "CH"),
    "44": ("United Kingdom", "GB"),
    "49": ("Germany", "DE"),
    "52": ("Mexico", "MX"),
    "55": ("Brazil", "BR"),
    "61": ("Australia", "AU"),
    "62": ("Indonesia", "ID"),
    "63": ("Philippines", "PH"),
    "81": ("Japan", "JP"),
    "82": ("South Korea", "KR"),
    "86": ("China", "CN"),
    "90": ("Turkey", "TR"),
    "91": ("India", "IN"),
    "92": ("Pakistan", "PK"),
    "971": ("United Arab Emirates", "AE"),
    "966": ("Saudi Arabia", "SA"),
    "974": ("Qatar", "QA"),
}
_location_defaults = {
    ("AE", "dubai"): {"city": "Dubai", "region": "Dubai"},
    ("AE", "abu dhabi"): {"city": "Abu Dhabi", "region": "Abu Dhabi"},
    ("DZ", "algiers"): {"city": "Algiers", "region": "Algiers Province"},
    ("DZ", "setif"): {"city": "Setif", "region": "Setif Province"},
    ("ZM", "lusaka"): {"city": "Lusaka", "region": "Lusaka Province"},
    ("DZ", "el eulma"): {"city": "El Eulma", "region": "Setif Province"},
    ("EG", "suez"): {"city": "Suez", "region": "Suez Governorate"},
    ("EG", "mansoura"): {"city": "Mansoura", "region": "Dakahlia Governorate"},
    ("EG", "cairo"): {"city": "Cairo", "region": "Cairo Governorate"},
    ("EG", "alexandria"): {"city": "Alexandria", "region": "Alexandria Governorate"},
    ("FR", "paris"): {"city": "Paris", "region": "Ile-de-France"},
    ("GB", "london"): {"city": "London", "region": "England"},
    ("DE", "berlin"): {"city": "Berlin", "region": "Berlin"},
    ("IT", "rome"): {"city": "Rome", "region": "Lazio"},
    ("ES", "madrid"): {"city": "Madrid", "region": "Community of Madrid"},
    ("ES", "barcelona"): {"city": "Barcelona", "region": "Catalonia"},
    ("PK", "karachi"): {"city": "Karachi", "region": "Sindh"},
    ("PK", "lahore"): {"city": "Lahore", "region": "Punjab"},
    ("PK", "islamabad"): {"city": "Islamabad", "region": "Islamabad Capital Territory"},
    ("MA", "casablanca"): {"city": "Casablanca", "region": "Casablanca-Settat"},
    ("MA", "rabat"): {"city": "Rabat", "region": "Rabat-Sale-Kenitra"},
    ("MA", "tanger"): {"city": "Tangier", "region": "Tanger-Tetouan-Al Hoceima"},
    ("MA", "tangier"): {"city": "Tangier", "region": "Tanger-Tetouan-Al Hoceima"},
    ("IN", "mumbai"): {"city": "Mumbai", "region": "Maharashtra"},
    ("IN", "delhi"): {"city": "Delhi", "region": "Delhi"},
    ("BD", "dhaka"): {"city": "Dhaka", "region": "Dhaka Division"},
    ("NG", "lagos"): {"city": "Lagos", "region": "Lagos State"},
    ("KE", "nairobi"): {"city": "Nairobi", "region": "Nairobi County"},
    ("ZA", "johannesburg"): {"city": "Johannesburg", "region": "Gauteng"},
    ("SA", "riyadh"): {"city": "Riyadh", "region": "Riyadh Province"},
    ("TR", "istanbul"): {"city": "Istanbul", "region": "Istanbul Province"},
    ("TR", "ankara"): {"city": "Ankara", "region": "Ankara Province"},
    ("US", "new york"): {"city": "New York", "region": "New York"},
    ("US", "los angeles"): {"city": "Los Angeles", "region": "California"},
    ("CA", "toronto"): {"city": "Toronto", "region": "Ontario"},
    ("AU", "sydney"): {"city": "Sydney", "region": "New South Wales"},
}
_postal_defaults = {
    ("ZM", "10101"): {"city": "Lusaka", "region": "Lusaka Province"},
}
_region_defaults = {
    "setif": ("Algeria", "DZ", "Setif Province"),
    "sétif": ("Algeria", "DZ", "Setif Province"),
    "\u0633\u0637\u064a\u0641": ("Algeria", "DZ", "Setif Province"),
}
_nationality_aliases.update({"marocain": "Moroccan", "marocaine": "Moroccan"})


def fallback_id(path: Path, lines: List[str]) -> str:
    digest = hashlib.sha256(("\n".join(lines) + str(path.name)).encode("utf-8")).hexdigest()[:12]
    return f"file-{digest}"


def _value_at(data: Dict[str, Any], path: Iterable[str]) -> str | None:
    current: Any = data
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    if isinstance(current, str) and current.strip():
        return current.strip()
    return None


def _first_array_value(data: Dict[str, Any], path: Iterable[str], field: str) -> str | None:
    current: Any = data
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    if not isinstance(current, list):
        return None
    for item in current:
        if isinstance(item, dict) and isinstance(item.get(field), str) and item[field].strip():
            return item[field].strip()
    return None


def stable_profile_id(data: Dict[str, Any], path: Path, lines: List[str]) -> Tuple[str, str]:
    national_id = _value_at(data, ("personal", "national_id"))
    if national_id:
        return _slug(f"nid-{national_id}"), "national_id"

    full_name = _value_at(data, ("personal", "full_name"))
    date_of_birth = _value_at(data, ("personal", "date_of_birth"))
    if full_name and date_of_birth:
        return _slug(f"name-dob-{full_name}-{date_of_birth}"), "full_name_date_of_birth"
    if full_name:
        return _slug(f"name-{full_name}"), "full_name"

    email = _first_array_value(data, ("contact", "emails"), "address")
    if email:
        return _slug(f"email-{email.lower()}"), "email"

    phone = _first_array_value(data, ("contact", "phones"), "number")
    if phone:
        return _slug(f"phone-{phone}"), "phone"

    return fallback_id(path, lines), "fallback"


def _slug(value: str) -> str:
    cleaned = _safe_name_re.sub("-", value.strip().lower()).strip(".-")
    return cleaned or "unknown"


def _alias_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def _place_key(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", str(value).strip().casefold())).strip()


def _country_alias(value: Any) -> Tuple[str, str] | None:
    key = _alias_key(value)
    return _country_aliases.get(key)


def _nationality_alias(value: Any) -> str | None:
    key = _alias_key(value)
    return _nationality_aliases.get(key)


def _calling_code_alias(value: Any) -> Tuple[str, str] | None:
    key = re.sub(r"\D+", "", str(value))
    return _calling_country_codes.get(key)


def _phone_calling_code_alias(value: Any) -> Tuple[str, str] | None:
    digits = re.sub(r"\D+", "", str(value))
    if not digits:
        return None
    for length in range(3, 1, -1):
        match = _calling_country_codes.get(digits[:length])
        if match:
            return match
    return None


def _location_country(value: Any) -> Tuple[str, str] | None:
    place = _place_key(value)
    if not place:
        return None
    for country_code, default_place in _location_defaults:
        if place == default_place:
            return (_country_codes[country_code], country_code)
    return None


def _line_labeled_value(lines: List[str], labels: set[str]) -> str | None:
    for line in lines:
        match = _label_value_re.search(line)
        if not match:
            continue
        label = _alias_key(match.group("label"))
        if label in labels:
            return match.group("value").strip()
    return None


def _blob_value(text: Any, field: str) -> str | None:
    if not isinstance(text, str) or "{" not in text or field not in text:
        return None
    match = re.search(rf"['\"]?{re.escape(field)}['\"]?\s*:\s*['\"]?(?P<value>[^,'\"}}]+)", text)
    if not match:
        return None
    value = match.group("value").strip()
    if _alias_key(value) in {"none", "null"}:
        return None
    return value


def _repair_address_blob(address: Dict[str, Any]) -> bool:
    for source_field in ("street", "city", "region", "postal_code", "country", "country_code"):
        blob = address.get(source_field)
        if not isinstance(blob, str) or "{" not in blob:
            continue
        repaired = False
        for target_field in ("street", "city", "region", "postal_code", "country", "country_code"):
            value = _blob_value(blob, target_field)
            if value and (not address.get(target_field) or address.get(target_field) == blob):
                address[target_field] = value
                repaired = True
        if repaired and address.get(source_field) == blob:
            address[source_field] = None
        return repaired
    return False


def repair_profile(profile: Dict[str, Any], lines: List[str]) -> List[str]:
    warnings: List[str] = []
    address = profile["address"]
    personal = profile["personal"]

    if _repair_address_blob(address):
        warnings.append("address_blob_repaired")

    country = _country_alias(address.get("country"))
    if country:
        address["country"], address["country_code"] = country
    elif isinstance(address.get("country_code"), str):
        code = address["country_code"].strip().upper()
        if code in _country_codes:
            address["country"] = address.get("country") or _country_codes[code]
            address["country_code"] = code
        else:
            calling_code = _calling_code_alias(code)
            if calling_code:
                address["country"], address["country_code"] = calling_code
                warnings.append("country_code_normalized_from_calling_code")

    if not address.get("country"):
        labeled_country = _line_labeled_value(lines, {"country", "pays"})
        country = _country_alias(labeled_country) if labeled_country else None
        if country:
            address["country"], address["country_code"] = country

    if not address.get("country"):
        for phone in profile["contact"]["phones"]:
            if not isinstance(phone, dict):
                continue
            country = _phone_calling_code_alias(phone.get("number"))
            if country:
                address["country"], address["country_code"] = country
                warnings.append("country_inferred_from_phone_code")
                break

    if not address.get("country"):
        region = _region_defaults.get(_place_key(address.get("region")))
        if region:
            address["country"], address["country_code"], address["region"] = region
            warnings.append("country_inferred_from_region")

    if not address.get("country"):
        city = _place_key(address.get("city"))
        for (country_code, default_city), defaults in _location_defaults.items():
            if city == default_city:
                address["country"] = _country_codes[country_code]
                address["country_code"] = country_code
                warnings.append("country_inferred_from_city")
                break

    country_code = str(address.get("country_code") or "").upper()
    city = _place_key(address.get("city"))
    postal_code = _place_key(address.get("postal_code"))
    defaults = _location_defaults.get((country_code, city)) or _postal_defaults.get((country_code, postal_code))
    if defaults:
        if not address.get("city"):
            address["city"] = defaults["city"]
        if not address.get("region") or _place_key(address.get("region")) in _region_defaults:
            address["region"] = defaults["region"]
            warnings.append("region_inferred_from_location")

    for field in ("street", "city", "region"):
        country = _country_alias(address.get(field))
        if not country:
            continue
        if not address.get("country"):
            address["country"], address["country_code"] = country
        elif not address.get("country_code"):
            address["country_code"] = country[1]
        address[field] = None
        warnings.append(f"country_moved_from_address_{field}")

    nationality = _nationality_alias(personal.get("nationality"))
    if nationality:
        personal["nationality"] = nationality
    elif not personal.get("nationality"):
        labeled_nationality = _line_labeled_value(lines, {"nationality", "nationalite"})
        nationality = _nationality_alias(labeled_nationality) if labeled_nationality else None
        if nationality:
            personal["nationality"] = nationality
        else:
            place_country = _country_alias(personal.get("place_of_birth")) or _location_country(personal.get("place_of_birth"))
            if place_country:
                personal["nationality"] = _country_nationalities.get(place_country[1])
                warnings.append("nationality_inferred_from_place")
            elif address.get("country_code") in _country_nationalities:
                personal["nationality"] = _country_nationalities[address["country_code"]]
                warnings.append("nationality_inferred_from_country")

    return warnings


def validate_profile(data: Any, path: Path, lines: List[str]) -> Tuple[Dict[str, Any], List[str]]:
    if not isinstance(data, dict):
        raise ValueError("Ollama response must be a JSON object")

    warnings: List[str] = []
    supplied_id = data.get("id")
    profile = normalize_profile(data)
    warnings.extend(repair_profile(profile, lines))
    if isinstance(supplied_id, (str, int)) and str(supplied_id).strip():
        profile["id"] = str(supplied_id).strip()
        profile["_id_strategy"] = "model_id"
    else:
        profile_id, strategy = stable_profile_id(profile, path, lines)
        profile["id"] = profile_id
        profile["_id_strategy"] = strategy
        if strategy == "fallback":
            warnings.append("missing_identity_generated")

    if not has_visible_data({key: value for key, value in profile.items() if not key.startswith("_") and key != "id"}):
        raise ValueError("profile must include at least one data field besides id")

    if warnings:
        existing = profile.get("_warnings")
        if isinstance(existing, list):
            profile["_warnings"] = [*existing, *warnings]
        else:
            profile["_warnings"] = warnings

    return profile, warnings
