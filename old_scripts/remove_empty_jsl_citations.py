#!/usr/bin/env python3
# ============================================================
# old_scripts/remove_empty_jsl_citations.py
# Remove JSL citation entries whose reference lists are empty.
# ============================================================
"""Remove entries with an empty references list from JSL citations."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent
    file_path = root / "active_data" / "jsl_citations.json"
    backup_path = root / "active_data" / "jsl_citations.json.bak"

    with file_path.open("r", encoding="utf-8") as handle:
        entries = json.load(handle)

    filtered = [entry for entry in entries if not (isinstance(entry, dict) and entry.get("references") == [])]
    removed = len(entries) - len(filtered)

    backup_path.write_bytes(file_path.read_bytes())
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(filtered, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"Removed {removed} empty-reference entries from {file_path}")
    print(f"Backup written to {backup_path}")


if __name__ == "__main__":
    main()
