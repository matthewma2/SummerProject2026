#!/usr/bin/env python3
"""Split unresolved references by whether they begin with an all-caps author name."""

import json
import re
from pathlib import Path


INPUT_PATH = Path("jsl_citations_data/5_unresolved_references.json")
ALL_CAPS_PATH = Path("jsl_citations_data/6a_all_caps_author_references.json")
OTHER_PATH = Path("jsl_citations_data/6b_other_references.json")


connectors = {"and", "et", "und", "y", "e", "with"}
particles = {"v", "von", "van", "de", "del", "der", "den", "di", "du"}
word_re = re.compile(r"[A-Za-zÀ-ÖØ-ÞĀ-ſ]+|[,.]")


def is_initial(letters: str) -> bool:
    return len(letters) == 1 and letters.upper() == letters


def is_allowed_author_word(token: str) -> tuple[bool, bool]:
    letters = "".join(ch for ch in token if ch.isalpha())
    if not letters:
        return False, False

    lower = letters.lower()

    if lower in connectors:
        return True, False

    if lower in particles:
        return True, False

    if is_initial(letters):
        return True, False

    if letters == letters.upper():
        return True, True

    return False, False


def starts_with_all_caps_author(reference: str) -> bool:
    tokens = word_re.findall(reference.strip())
    saw_upper_name = False
    previous_was_upper_name = False

    for token in tokens:
        if token == ",":
            return saw_upper_name

        if token == ".":
            if previous_was_upper_name:
                return True
            previous_was_upper_name = False
            continue

        allowed, is_upper_name = is_allowed_author_word(token)
        if not allowed:
            return False

        saw_upper_name = saw_upper_name or is_upper_name
        previous_was_upper_name = is_upper_name

    return saw_upper_name


def main() -> None:
    references = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    if not isinstance(references, list):
        raise ValueError(f"Expected a JSON list in {INPUT_PATH}")

    all_caps = []
    other = []
    skipped = 0

    for reference in references:
        if not isinstance(reference, str):
            skipped += 1
            continue

        if starts_with_all_caps_author(reference):
            all_caps.append(reference)
        else:
            other.append(reference)

    ALL_CAPS_PATH.write_text(
        json.dumps(all_caps, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    OTHER_PATH.write_text(
        json.dumps(other, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Read {len(references)} unresolved references from {INPUT_PATH}")
    print(f"Wrote {len(all_caps)} all-caps author references to {ALL_CAPS_PATH}")
    print(f"Wrote {len(other)} other references to {OTHER_PATH}")
    if skipped:
        print(f"Skipped {skipped} non-string entries")


if __name__ == "__main__":
    main()
