#!/usr/bin/env python3
"""Remove duplicate reference strings while preserving their original order."""

import json
import re
import unicodedata
from pathlib import Path


INPUT_PATH = Path("jsl_citations_data_2/3_references_cleaned.json")
OUTPUT_PATH = Path("jsl_citations_data_2/4_references_deduplicated.json")
LOG_PATH = Path("jsl_citations_pipeline_logs/4_removed_duplicates_log.json")


def duplicate_key(reference: str) -> str:
    """Return a conservative key that absorbs common OCR formatting variants."""
    normalized = unicodedata.normalize("NFKC", reference)
    normalized = re.sub(r"(\w)-\s+(\w)", r"\1\2", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.casefold()


def main() -> None:
    references = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    if not isinstance(references, list):
        raise ValueError(f"Expected a JSON list in {INPUT_PATH}")

    unique_references = []
    first_by_key = {}
    removed = []
    skipped = 0

    for input_index, reference in enumerate(references):
        if not isinstance(reference, str):
            skipped += 1
            continue

        key = duplicate_key(reference)
        first = first_by_key.get(key)
        if first is None:
            first_by_key[key] = {
                "input_index": input_index,
                "reference": reference,
            }
            unique_references.append(reference)
            continue

        removed.append({
            "input_index": input_index,
            "kept_input_index": first["input_index"],
            "match_type": "exact" if reference == first["reference"] else "normalized",
            "deleted_reference": reference,
            "kept_reference": first["reference"],
        })

    OUTPUT_PATH.write_text(
        json.dumps(unique_references, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    exact_count = sum(item["match_type"] == "exact" for item in removed)
    normalized_count = len(removed) - exact_count
    log = {
        "input_path": str(INPUT_PATH),
        "output_path": str(OUTPUT_PATH),
        "input_references": len(references),
        "unique_references": len(unique_references),
        "duplicates_removed": len(removed),
        "exact_duplicates_removed": exact_count,
        "normalized_duplicates_removed": normalized_count,
        "skipped_non_strings": skipped,
        "removed": removed,
    }
    LOG_PATH.write_text(
        json.dumps(log, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Read {len(references)} references from {INPUT_PATH}")
    print(f"Removed {len(removed)} duplicates ({exact_count} exact, {normalized_count} normalized)")
    print(f"Wrote {len(unique_references)} unique references to {OUTPUT_PATH}")
    print(f"Wrote duplicate-removal log to {LOG_PATH}")
    if skipped:
        print(f"Skipped {skipped} non-string entries")


if __name__ == "__main__":
    main()
