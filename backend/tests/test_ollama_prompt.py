from backend.pipeline.ollama import build_prompt


def test_prompt_contains_strict_scalar_and_geography_rules() -> None:
    prompt = build_prompt([("source.txt", ["city: LUSAKA", "country_code: 260"])])

    assert "Return exactly one raw JSON object" in prompt
    assert "Never put an object, array, dictionary dump, or JSON string inside a scalar field" in prompt
    assert "country_code is ISO 3166-1 alpha-2" in prompt
    assert "calling code such as +260 or country_code 260" in prompt
    assert "Lusaka + 10101 or calling code 260 implies Zambia / ZM" in prompt
    assert "Do not confuse nationality with residence/address country" in prompt
