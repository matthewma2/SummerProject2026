#!/usr/bin/env python3
"""Convert active/works.json records to BibTeX."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


TYPE_MAP = {
    "Article": "article",
    "Book": "book",
    "Book Chapter": "incollection",
    "Chapter": "incollection",
    "Encyclopedia Entry": "inreference",
    "Fragment": "misc",
    "Letters": "misc",
    "Manuscript": "misc",
    "Thesis": "thesis",
}

FIELD_ORDER = ("author", "title", "journal", "year", "volume", "address", "pages")


def bibtex_type(publication_type: str | None) -> str:
    return TYPE_MAP.get(publication_type or "", "misc")


def normalize_pages(pages: Any) -> str | None:
    if pages is None:
        return None
    text = str(pages).strip()
    if not text:
        return None
    return re.sub(r"(?<=\d)-(?=\d)", "--", text)


def escape_bibtex(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    replacements = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "%": r"\%",
        "&": r"\&",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def record_to_fields(record: dict[str, Any]) -> dict[str, str]:
    fields = {
        "author": escape_bibtex(record.get("author_name")),
        "title": escape_bibtex(record.get("title")),
        "journal": escape_bibtex(record.get("journal")),
        "year": escape_bibtex(record.get("year")),
        "volume": escape_bibtex(record.get("volume")),
        "address": escape_bibtex(record.get("location")),
        "pages": escape_bibtex(normalize_pages(record.get("pages"))),
    }
    if record.get("publication_type") == "Article":
        fields["address"] = None
    else:
        fields["journal"] = None
        fields["volume"] = None
    return {key: value for key, value in fields.items() if value is not None}


def record_to_bibtex(record: dict[str, Any]) -> str:
    entry_id = record.get("entry_id")
    if not entry_id:
        raise ValueError(f"Record is missing entry_id: {record!r}")

    entry_type = bibtex_type(record.get("publication_type"))
    fields = record_to_fields(record)
    if not fields:
        return f"@{entry_type}{{{entry_id}\n}}"

    width = max(len(field) for field in fields)
    lines = [f"@{entry_type}{{{entry_id},"]
    for index, field in enumerate(FIELD_ORDER):
        if field not in fields:
            continue
        suffix = "," if index < len(FIELD_ORDER) - 1 else ""
        lines.append(f"  {field:<{width}} = {{{fields[field]}}}{suffix}")

    # Remove the trailing comma from the last emitted field, even when later
    # fields were absent.
    lines[-1] = lines[-1].rstrip(",")
    lines.append("}")
    return "\n".join(lines)


def load_records(input_path: Path) -> list[dict[str, Any]]:
    with input_path.open("r", encoding="utf-8") as infile:
        data = json.load(infile)

    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list in {input_path}")

    records = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError(f"Expected every record to be an object: {item!r}")
        records.append(item)
    return records


def write_bibtex(records: list[dict[str, Any]], output_path: Path) -> None:
    bibtex = "\n\n".join(record_to_bibtex(record) for record in records)
    output_path.write_text(f"{bibtex}\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert works.json records to a BibTeX .bib file."
    )
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path(__file__).with_name("works.json"),
        help="Input JSON file. Defaults to active/works.json.",
    )
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=Path(__file__).with_name("works.bib"),
        help="Output BibTeX file. Defaults to active/works.bib.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = load_records(args.input)
    write_bibtex(records, args.output)
    print(f"Wrote {len(records)} BibTeX entries to {args.output}")


if __name__ == "__main__":
    main()
