#!/usr/bin/env python3
"""Split other unresolved references into the same length bands as pipeline 1."""

import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "jsl_citations_data_2"
LOG_DIR = Path(__file__).resolve().parent.parent / "jsl_citations_pipeline_logs"

INPUT_PATH = DATA_DIR / "6b_other_references.json"
FURTHER_INTERNAL_REFS_PATH = LOG_DIR / "6b_further_internal_refs.json"
JOURNAL_REFS_PATH = LOG_DIR / "6b_journal_refs.json"
MORE_THAN_43_PATH = DATA_DIR / "7_long_valid_refs.json"


def main() -> None:
    items = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise ValueError(f"Expected a JSON list in {INPUT_PATH}")

    less_than_25 = []
    between_25_and_43 = []
    more_than_43 = []
    skipped = 0

    for item in items:
        if not isinstance(item, str):
            skipped += 1
            continue

        item_len = len(item)
        if item_len < 25:
            less_than_25.append(item)
        elif item_len <= 43:
            between_25_and_43.append(item)
        else:
            more_than_43.append(item)

    outputs = (
        (FURTHER_INTERNAL_REFS_PATH, less_than_25),
        (JOURNAL_REFS_PATH, between_25_and_43),
        (MORE_THAN_43_PATH, more_than_43),
    )
    for path, values in outputs:
        path.write_text(
            json.dumps(values, indent=4, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    print(
        f"total={len(items)} "
        f"less_than_25={len(less_than_25)} "
        f"between_25_and_43={len(between_25_and_43)} "
        f"more_than_43={len(more_than_43)}"
    )
    print(FURTHER_INTERNAL_REFS_PATH)
    print(JOURNAL_REFS_PATH)
    print(MORE_THAN_43_PATH)
    if skipped:
        print(f"skipped_non_strings={skipped}")


if __name__ == "__main__":
    main()
