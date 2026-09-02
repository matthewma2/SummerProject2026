#!/usr/bin/env python3
"""Compile all JSL reference strings into a flat JSON list."""

import json
from pathlib import Path


INPUT_PATH = Path("jsl_citations_data_2/1_jsl_citations_original.json")
OUTPUT_PATH = Path("jsl_citations_data_2/2_references_compiled.json")


def main() -> None:
    entries = json.loads(INPUT_PATH.read_text(encoding="utf-8"))

    references = []
    skipped = 0

    for entry in entries:
        if not isinstance(entry, dict):
            skipped += 1
            continue

        for ref_obj in entry.get("references", []):
            if not isinstance(ref_obj, dict):
                skipped += 1
                continue

            reference = ref_obj.get("reference")
            if isinstance(reference, str) and reference.strip():
                references.append(reference)
            else:
                skipped += 1

    OUTPUT_PATH.write_text(
        json.dumps(references, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Read {len(entries)} source entries from {INPUT_PATH}")
    print(f"Wrote {len(references)} reference strings to {OUTPUT_PATH}")
    if skipped:
        print(f"Skipped {skipped} malformed or empty reference entries")


if __name__ == "__main__":
    main()
