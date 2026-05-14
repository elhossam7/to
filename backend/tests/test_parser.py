from pathlib import Path

from backend.pipeline.parser import read_lines


def test_read_lines_keeps_short_and_numeric_context(tmp_path: Path) -> None:
    source = tmp_path / "profile.txt"
    source.write_text("\n 75008 \n Dr \n St \n 42 rue de Paris \n\n", encoding="utf-8")

    assert read_lines(source) == ["75008", "Dr", "St", "42 rue de Paris"]
