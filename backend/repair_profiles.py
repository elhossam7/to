from __future__ import annotations

import json

from backend.pipeline.validator import repair_profile
from backend.settings import settings


def main() -> None:
    settings.ensure_dirs()
    repaired = 0
    for path in sorted(settings.profiles_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("address"), dict) or not isinstance(data.get("personal"), dict):
            continue
        before = json.dumps(data, sort_keys=True)
        warnings = repair_profile(data, [])
        if json.dumps(data, sort_keys=True) == before:
            continue
        existing = data.get("_warnings")
        if isinstance(existing, list):
            data["_warnings"] = list(dict.fromkeys([*existing, *warnings]))
        elif warnings:
            data["_warnings"] = warnings
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        repaired += 1
        print(f"repaired {path.name}: {', '.join(warnings)}")
    print(f"repaired_profiles={repaired}")


if __name__ == "__main__":
    main()
