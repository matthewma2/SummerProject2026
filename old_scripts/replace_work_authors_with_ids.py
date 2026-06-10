#!/usr/bin/env python3
"""Replace work author names with ids from authors.json where matches are safe."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PARTICLES = {"v", "von", "van", "de", "del", "della", "di", "du", "le", "la"}


def normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"['’]", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(value: Any) -> list[str]:
    return normalize(value).split()


def unique_ids(ids: list[str]) -> list[str]:
    return sorted(set(ids))


def last_token(value: Any) -> str | None:
    parts = tokens(value)
    return parts[-1] if parts else None


def initials_last_form(value: Any) -> str | None:
    parts = [part for part in tokens(value) if part not in PARTICLES]
    if len(parts) < 2:
        return None
    initials = [part[0] for part in parts[:-1] if part]
    if not initials:
        return None
    return " ".join([*initials, parts[-1]])


def build_indexes(authors: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    exact: dict[str, list[str]] = defaultdict(list)
    initial_last: dict[str, list[str]] = defaultdict(list)
    last_name: dict[str, list[str]] = defaultdict(list)

    for author in authors:
        author_id = author.get("id")
        if not author_id:
            continue

        names = [author.get("full_name"), *(author.get("alternative_names") or [])]
        for name in names:
            normalized = normalize(name)
            if normalized:
                exact[normalized].append(author_id)

            compact = initials_last_form(name)
            if compact:
                initial_last[compact].append(author_id)

            last = last_token(name)
            if last:
                last_name[last].append(author_id)

    return {
        "exact": {key: unique_ids(value) for key, value in exact.items()},
        "initial_last": {key: unique_ids(value) for key, value in initial_last.items()},
        "last_name": {key: unique_ids(value) for key, value in last_name.items()},
    }


def split_author_names(author_name: Any) -> list[str]:
    text = str(author_name or "").strip()
    if not text:
        return []
    if " and " not in text and ", and " not in text:
        return [text]
    text = re.sub(r",\s+and\s+", ", ", text)
    text = re.sub(r"\s+and\s+", ", ", text)
    return [part.strip() for part in text.split(",") if part.strip()]


def match_author(author_name: Any, indexes: dict[str, dict[str, list[str]]]) -> tuple[str | None, str]:
    normalized = normalize(author_name)
    if not normalized:
        return None, "missing_author"

    for method, key in (
        ("exact", normalized),
        ("initial_last", initials_last_form(author_name)),
        ("unique_last_name", last_token(author_name)),
    ):
        if not key:
            continue
        ids = indexes["last_name" if method == "unique_last_name" else method].get(key, [])
        if len(ids) == 1:
            return ids[0], method
        if len(ids) > 1:
            return None, f"ambiguous_{method}"

    return None, "unmatched"


def match_author_value(
    author_value: Any, indexes: dict[str, dict[str, list[str]]]
) -> tuple[str | list[str] | None, str]:
    parts = split_author_names(author_value)
    if len(parts) <= 1:
        return match_author(author_value, indexes)

    ids = []
    reasons = []
    for part in parts:
        author_id, method = match_author(part, indexes)
        reasons.append(method)
        if author_id is None:
            return None, f"multi_{method}"
        ids.append(author_id)

    return ids, "multi_author"


def replace_authors(
    works: list[dict[str, Any]], indexes: dict[str, dict[str, list[str]]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Counter[str]]:
    updated = []
    report = []
    method_counts: Counter[str] = Counter()

    for work in works:
        author_name = work.get("author")
        author_id, method = match_author_value(author_name, indexes)
        method_counts[method] += 1

        if author_id is None:
            report.append(
                {
                    "work_id": work.get("id"),
                    "author": author_name,
                    "reason": method,
                }
            )
            updated.append(work)
            continue

        new_work = dict(work)
        new_work["author"] = author_id
        updated.append(new_work)

    return updated, report, method_counts


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as infile:
        return json.load(infile)


def write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as outfile:
        json.dump(data, outfile, indent=2, ensure_ascii=False)
        outfile.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replace works.json author names with ids from authors.json."
    )
    base_dir = Path(__file__).resolve().parent
    parser.add_argument("--works", type=Path, default=base_dir / "works.json")
    parser.add_argument("--authors", type=Path, default=base_dir / "authors.json")
    parser.add_argument(
        "--report",
        type=Path,
        default=base_dir / "work_author_id_unmatched.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    works = load_json(args.works)
    authors = load_json(args.authors)
    if not isinstance(works, list):
        raise ValueError(f"Expected a list in {args.works}")
    if not isinstance(authors, list):
        raise ValueError(f"Expected a list in {args.authors}")

    updated, report, method_counts = replace_authors(works, build_indexes(authors))
    write_json(args.works, updated)
    write_json(args.report, report)

    matched = sum(count for method, count in method_counts.items() if not method.startswith(("unmatched", "ambiguous", "missing")))
    print(f"Updated {matched} of {len(works)} work author values.")
    for method, count in sorted(method_counts.items()):
        print(f"{method}: {count}")
    print(f"Wrote {len(report)} unresolved author values to {args.report}")


if __name__ == "__main__":
    main()
