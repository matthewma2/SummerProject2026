#!/usr/bin/env python3
"""Convert active_data/works.json records to BibTeX using author mapping."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

# Adjusted to lowercase keys to perfectly match the 'type' fields in works.json
TYPE_MAP = {
    "article": "article",
    "book": "book",
    "book chapter": "incollection",
    "chapter": "incollection",
    "encyclopedia entry": "incollection",
    "fragment": "misc",
    "letters": "misc",
    "manuscript": "misc",
    "thesis": "thesis",
    "dialogue": "misc",
    "treatise": "book",
    "novel": "book",
}

FIELD_ORDER = ("author", "title", "journal", "year", "volume", "address", "pages")


def bibtex_type(publication_type: str | None) -> str:
    return TYPE_MAP.get((publication_type or "").lower(), "misc")


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
    }
    
    for orig, rep in replacements.items():
        text = text.replace(orig, rep)
    return text


def format_author_fallback(slug: str) -> str:
    """Fallback formatter if an author ID is missing from authors.json."""
    parts = slug.split("-")
    formatted_parts = []
    for part in parts:
        if part.lower() in ("von", "de", "di", "van"):
            formatted_parts.append(part)
        elif len(part) == 1:
            formatted_parts.append(part.upper() + ".")
        else:
            formatted_parts.append(part.capitalize())
    return " ".join(formatted_parts)


def record_to_bibtex(record: dict[str, Any], authors_map: dict[str, str]) -> str:
    entry_id = record.get("id", "unknown")
    pub_type = record.get("type", "misc")
    bib_type = bibtex_type(str(pub_type))
    
    # Resolve author IDs against the loaded authors data
    authors_list = record.get("authors", [])
    formatted_authors = []
    for author_id in authors_list:
        if author_id in authors_map:
            formatted_authors.append(authors_map[author_id])
        else:
            # Fallback to string formatting if ID isn't found in authors.json
            formatted_authors.append(format_author_fallback(author_id))
            
    author_str = " and ".join(formatted_authors)
    
    # Gather fields (Excluding 'notes')
    fields = {}
    if author_str:
        fields["author"] = author_str
    if "title" in record:
        fields["title"] = record["title"]
    if "journal" in record:
        fields["journal"] = record["journal"]
    if "year" in record:
        fields["year"] = str(record["year"])
    if "volume" in record:
        fields["volume"] = record["volume"]
    if "location" in record:
        fields["address"] = record["location"]
    if "pages" in record:
        fields["pages"] = normalize_pages(record["pages"])
    if "publisher" in record:
        fields["publisher"] = record["publisher"]
    if "number" in record:
        fields["number"] = record["number"]
    if "series" in record:
        fields["series"] = record["series"]
    if "booktitle" in record:
        fields["booktitle"] = record["booktitle"]

    # Escape specialized LaTeX characters
    escaped_fields = {}
    for k, v in fields.items():
        ev = escape_bibtex(v)
        if ev:
            escaped_fields[k] = ev

    # Build entry blocks
    lines = [f"@{bib_type}{{{entry_id},"]
    
    all_keys = list(escaped_fields.keys())
    ordered_keys = [k for k in FIELD_ORDER if k in escaped_fields]
    other_keys = sorted([k for k in all_keys if k not in FIELD_ORDER])
    
    for k in ordered_keys + other_keys:
        val = escaped_fields[k]
        if k == "title":
            lines.append(f"    {k} = {{{{{val}}}}},")
        else:
            lines.append(f"    {k} = {{{val}}},")
            
    return "\n".join(lines) + "\n}"


def load_authors(authors_path: Path) -> dict[str, str]:
    """Loads authors.json and builds a flat map of id -> full_name."""
    if not authors_path.exists():
        print(f"Warning: {authors_path} not found. Falling back to ID auto-formatting.")
        return {}
        
    with authors_path.open("r", encoding="utf-8") as infile:
        data = json.load(infile)
        
    authors_map = {}
    # Case 1: authors.json is a list of objects: [{"id": "...", "full_name": "..."}, ...]
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "id" in item:
                name = item.get("full_name") or item.get("name") or item["id"]
                authors_map[item["id"]] = str(name)
                
    # Case 2: authors.json is a top-level dictionary: {"author-id": {"full_name": "..."}}
    elif isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                name = v.get("full_name") or v.get("name") or k
                authors_map[k] = str(name)
            else:
                authors_map[k] = str(v)
                
    return authors_map


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


def write_bibtex(records: list[dict[str, Any]], authors_map: dict[str, str], output_path: Path) -> None:
    bibtex = "\n\n".join(record_to_bibtex(record, authors_map) for record in records)
    output_path.write_text(f"{bibtex}\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert works.json records to a BibTeX .bib file."
    )
    
    # Safe multi-level traversal: active_scripts/works_to_bib.py -> parent -> parent -> active_data/
    project_root = Path(__file__).resolve().parent.parent
    
    default_input = project_root / "active_data" / "works.json"
    default_authors = project_root / "active_data" / "authors.json"
    default_output = project_root / "active_data" / "works.bib"
    
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=default_input,
        help="Input JSON file. Defaults to active_data/works.json.",
    )
    parser.add_argument(
        "--authors",
        type=Path,
        default=default_authors,
        help="Authors map JSON file. Defaults to active_data/authors.json.",
    )
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=default_output,
        help="Output BibTeX file. Defaults to active_data/works.bib.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        authors_map = load_authors(args.authors)
        records = load_records(args.input)
        write_bibtex(records, authors_map, args.output)
        print(f"Successfully converted {len(records)} records to {args.output}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()