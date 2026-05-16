from backend.pipeline.ollama import build_prompt


def test_prompt_contains_strict_scalar_and_geography_rules() -> None:
    prompt = build_prompt([("source.txt", ["city: LUSAKA", "country_code: 260"])])

    assert "Output exactly one raw JSON object" in prompt
    assert "never put objects, arrays, dictionary dumps, or JSON strings inside scalar fields".lower() in prompt.lower()
    assert "country_code is ISO 3166-1 alpha-2" in prompt
    assert "+260 or country_code 260 -> Zambia/ZM/Zambian" in prompt
    assert "Apply this rule globally" in prompt
    assert "+20/Suez/Mansoura -> Egypt/EG/Egyptian" in prompt
