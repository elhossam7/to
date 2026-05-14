from __future__ import annotations

from pathlib import Path
from typing import List

from backend.settings import settings


def read_lines(path: Path) -> List[str]:
    if path.stat().st_size > settings.max_file_size:
        raise ValueError(f"file exceeds MAX_FILE_SIZE ({settings.max_file_size} bytes)")
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
