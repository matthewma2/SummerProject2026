#!/usr/bin/env python3
"""Extract JSL citations whose source id contains 1936."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    input_path = root / "active_data" / "jsl_citations.json"
    output_path = root / "active_data" / "jsl_citations_1936.json"

    with input_path.open("r", encoding="utf-8") as handle:
        entries = json.load(handle)

    filtered = [entry for entry in entries if isinstance(entry, dict) and "source" in entry and "1936" in str(entry["source"])]

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(filtered, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"Wrote {len(filtered)} entries to {output_path}")


if __name__ == "__main__":
    main()
