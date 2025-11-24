from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


INSIGHTS_DIR = Path("data/insights")
ARCHIVE_DIR = INSIGHTS_DIR / "archive"


def is_low_quality_pack(pack: Dict[str, Any]) -> bool:
    """
    Decide if an insight pack is too low quality to keep in the main dropdown.

    Rules (you can tweak later):
    - Missing fiscal_year or fiscal_quarter  -> archive
    - company_hint is completely missing or just 'UNKNOWN' / '--'  -> archive
    """
    fiscal_year = pack.get("fiscal_year")
    fiscal_quarter = pack.get("fiscal_quarter")
    company_hint = (pack.get("company_hint") or "").strip()

    # If we have no year/quarter, the pack is not useful for the UI
    if not fiscal_year or not fiscal_quarter:
        return True

    # Very low-info company labels
    if company_hint.upper() in {"UNKNOWN", "--", ""}:
        return True

    return False


def main() -> None:
    if not INSIGHTS_DIR.exists():
        print("No data/insights directory found. Nothing to clean.")
        return

    ARCHIVE_DIR.mkdir(exist_ok=True)

    total = 0
    archived = 0

    for path in sorted(INSIGHTS_DIR.glob("*.json")):
        total += 1

        try:
            data = json.loads(path.read_text())
        except Exception as e:  # noqa: BLE001
            print(f"[WARN] Could not read {path.name}: {e}. Archiving it.")
            target = ARCHIVE_DIR / path.name
            path.rename(target)
            archived += 1
            continue

        if is_low_quality_pack(data):
            target = ARCHIVE_DIR / path.name
            print(f"[ARCHIVE] {path.name} -> {target}")
            path.rename(target)
            archived += 1
        else:
            # Keep this one
            print(f"[KEEP] {path.name}")

    print("\nSummary:")
    print(f"  Total packs scanned : {total}")
    print(f"  Archived (low-quality): {archived}")
    print(f"  Remaining in main dir: {total - archived}")


if __name__ == "__main__":
    main()
