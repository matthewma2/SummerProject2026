#!/usr/bin/env python3
"""Split long references by whether they begin with an author name."""

import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLASSIFIER_PATH = Path(__file__).resolve().parent / "_helpers" / "author_prefix_classifier.py"
DATA_DIR = PROJECT_ROOT / "jsl_citations_data"

INPUT_PATH = DATA_DIR / "7_long_valid_refs.json"
WITH_AUTHORS_PATH = DATA_DIR / "8a_with_authors.json"
WITHOUT_AUTHORS_PATH = DATA_DIR / "8b_no_authors.json"


def load_classifier():
    """Load the original pipeline's author-prefix classifier."""
    spec = importlib.util.spec_from_file_location("jsl_author_classifier", CLASSIFIER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load classifier from {CLASSIFIER_PATH}")

    classifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(classifier)
    return classifier


def main() -> None:
    references = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    if not isinstance(references, list):
        raise ValueError(f"Expected a JSON list in {INPUT_PATH}")

    classifier = load_classifier()
    with_authors = []
    without_authors = []
    skipped = 0

    for reference in references:
        if not isinstance(reference, str):
            skipped += 1
            continue

        if classifier.starts_with_author(reference):
            with_authors.append(reference)
        else:
            without_authors.append(reference)

    for path, values in (
        (WITH_AUTHORS_PATH, with_authors),
        (WITHOUT_AUTHORS_PATH, without_authors),
    ):
        path.write_text(
            json.dumps(values, indent=4, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    print(
        f"total={len(references)} "
        f"with_authors={len(with_authors)} "
        f"without_authors={len(without_authors)}"
    )
    print(WITH_AUTHORS_PATH)
    print(WITHOUT_AUTHORS_PATH)
    if skipped:
        print(f"skipped_non_strings={skipped}")


if __name__ == "__main__":
    main()
