#!/usr/bin/env python3
"""Add journal and volume fields to article records in works.json."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PUBLISHED_IN_RE = re.compile(r"\bpublished in\s+", re.IGNORECASE)
STOP_RE = re.compile(
    r"\s+(?:Reprinted|Includes quote|Quote:|See also|See |Cf\.|OCR |Author block|Entry contains)\b",
    re.IGNORECASE,
)
VOLUME_RE = re.compile(
    r"(?:,\s*)?(?P<prefix>(?:n\.?\s*s\.?|new ser\.|new series|\d+\s*s\.)\s+)?"
    r"vol\.?\s+(?P<volume>[A-Za-z0-9IVXLCDM]+(?:\s+(?:part|no\.?|sec\.)\s*[\w.-]+)?)",
    re.IGNORECASE,
)


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip(" ,.;")
    return value or None


def strip_trailing_date(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r",?\s*\(?\d{4}(?:-\d+)?\)?$", "", value).strip(" ,.;")
    value = re.sub(
        r",?\s*(?:\d{1,2}\s+)?[A-Z][a-z]+\s+\d{4}$", "", value
    ).strip(" ,.;")
    return value or None


def published_segment(notes: str | None) -> str | None:
    if not notes:
        return None

    match = PUBLISHED_IN_RE.search(notes)
    if not match:
        return None

    segment = notes[match.end() :]
    stop = STOP_RE.search(segment)
    if stop:
        segment = segment[: stop.start()]
    return clean_text(segment)


def unwrap_ibid(segment: str) -> str:
    match = re.match(r"Ibid\.\s*\((?P<inner>[^)]+)\)", segment, re.IGNORECASE)
    if match:
        return match.group("inner")
    return segment


def split_journal_volume(segment: str | None) -> tuple[str | None, str | None]:
    if segment is None:
        return None, None

    segment = unwrap_ibid(segment)
    volume_match = VOLUME_RE.search(segment)
    if not volume_match:
        journal = strip_trailing_date(clean_text(segment))
        return journal, None

    journal = clean_text(segment[: volume_match.start()])
    journal = strip_trailing_date(journal)

    prefix = clean_text(volume_match.group("prefix"))
    volume = clean_text(volume_match.group("volume"))
    if prefix and volume:
        volume = f"{prefix} {volume}"

    return journal, volume


def extract_journal_volume(notes: str | None) -> tuple[str | None, str | None]:
    return split_journal_volume(published_segment(notes))


def with_article_fields(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("publication_type") != "Article":
        return record

    journal, volume = extract_journal_volume(record.get("notes"))
    updated: dict[str, Any] = {}
    for key, value in record.items():
        if key in {"journal", "volume"}:
            continue
        updated[key] = value
        if key == "year":
            updated["journal"] = journal
            updated["volume"] = volume

    if "year" not in updated:
        updated["journal"] = journal
        updated["volume"] = volume
    return updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract article journal and volume fields from notes."
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=Path(__file__).with_name("works.json"),
        help="Path to works.json. Defaults to active/works.json.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with args.path.open("r", encoding="utf-8") as infile:
        records = json.load(infile)

    if not isinstance(records, list):
        raise ValueError(f"Expected a JSON list in {args.path}")

    updated = [with_article_fields(record) for record in records]
    with args.path.open("w", encoding="utf-8") as outfile:
        json.dump(updated, outfile, indent=2, ensure_ascii=False)
        outfile.write("\n")

    article_count = sum(1 for record in updated if record.get("publication_type") == "Article")
    journals = sum(
        1
        for record in updated
        if record.get("publication_type") == "Article" and record.get("journal") is not None
    )
    volumes = sum(
        1
        for record in updated
        if record.get("publication_type") == "Article" and record.get("volume") is not None
    )
    print(
        f"Updated {article_count} article records: "
        f"{journals} journals, {volumes} volumes extracted."
    )


if __name__ == "__main__":
    main()
