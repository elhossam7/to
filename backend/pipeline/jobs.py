from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class ProcessingJob:
    paths: List[Path]
    source: str
    batch_id: str

    @property
    def label(self) -> str:
        if len(self.paths) == 1:
            return self.paths[0].name
        return f"{len(self.paths)} files"
