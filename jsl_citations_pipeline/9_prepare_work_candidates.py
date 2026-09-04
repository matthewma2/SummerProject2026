#!/usr/bin/env python3
"""Prepare parsed JSL references for review and eventual works-database import."""

import json
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "jsl_citations_data"
LOG_DIR = PROJECT_ROOT / "jsl_citations_pipeline_logs"
AUTHORS_PATH = PROJECT_ROOT / "databases" / "authors.json"
WORKS_PATH = PROJECT_ROOT / "databases" / "works.json"
ORIGINAL_PATH = DATA_DIR / "1_jsl_citations_original.json"

PARSED_INPUTS = (
    ("all_caps", DATA_DIR / "parsed_all_caps_author_references.json"),
    ("with_authors", DATA_DIR / "9a_parsed_with_authors.json"),
    ("recovered_or_title_first", DATA_DIR / "9b_parsed_no_authors.json"),
)

READY_PATH = DATA_DIR / "10a_works_ready_to_add.json"
REVIEW_PATH = DATA_DIR / "10b_works_needing_review.json"
EXISTING_PATH = LOG_DIR / "9_existing_works_matched.json"
DUPLICATES_PATH = LOG_DIR / "9_parsed_duplicates.json"
AUDIT_PATH = LOG_DIR / "9_works_ready_to_add_audit.json"
INVALID_CONTEXTUAL_PATH = DATA_DIR / "invalid_or_contextual_references.json"

ALL_CAPS_INPUT_PATH = DATA_DIR / "6a_all_caps_author_references.json"
WITH_AUTHORS_INPUT_PATH = DATA_DIR / "8a_with_authors.json"
NO_AUTHOR_UNRESOLVED_PATH = LOG_DIR / "8b_unresolved_after_parse.json"
NO_AUTHOR_CONTEXTUAL_PATH = LOG_DIR / "8b_contextual_references.json"
NO_AUTHOR_FRAGMENTS_PATH = LOG_DIR / "8b_fragments.json"


SPECIAL = str.maketrans({
    "Ł": "L", "ł": "l", "Ø": "O", "ø": "o", "Đ": "D", "đ": "d",
    "Æ": "Ae", "æ": "ae", "Œ": "Oe", "œ": "oe", "0": "O",
})
AUTHOR_SUFFIXES = {"jr", "junior", "sr", "senior", "ed", "editor"}
AUTHOR_PARTICLES = {"de", "del", "den", "der", "di", "du", "la", "le", "van", "von"}
VALID_TYPES = {
    "article", "book", "book chapter", "inproceedings", "manuscript",
    "thesis", "encyclopedia entry", "pamphlet", "textbook", "monograph",
}


def normalized_text(value):
    value = str(value).translate(SPECIAL)
    value = "".join(
        char for char in unicodedata.normalize("NFD", value)
        if unicodedata.category(char) != "Mn"
    )
    value = re.sub(r"(\w)-\s+(\w)", r"\1\2", value)
    value = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", value)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_author_indexes(authors):
    by_id = {author["id"]: author for author in authors}
    aliases = defaultdict(set)
    surnames = defaultdict(set)

    for author in authors:
        author_id = author["id"]
        full_name = author.get("full_name") or author.get("name") or ""
        names = [full_name] + (author.get("alternative_names") or [])
        for name in names:
            name_norm = normalized_text(name)
            if name_norm:
                aliases[name_norm].add(author_id)

        full_tokens = normalized_text(full_name).split()
        if full_tokens:
            surnames[full_tokens[-1]].add(author_id)
        for alternative in author.get("alternative_names") or []:
            alt_tokens = normalized_text(alternative).split()
            if len(alt_tokens) == 1:
                surnames[alt_tokens[0]].add(author_id)

    return by_id, aliases, surnames


def author_parts(raw_name):
    raw_name = str(raw_name).strip()
    if "," in raw_name:
        family, given = raw_name.split(",", 1)
        raw_name = f"{given} {family}"

    tokens = normalized_text(raw_name).split()
    while tokens and tokens[-1] in AUTHOR_SUFFIXES:
        tokens.pop()
    if not tokens:
        return [], ""
    return tokens[:-1], tokens[-1]


def given_names_compatible(raw_given, full_name):
    candidate = normalized_text(full_name).split()[:-1]
    raw_given = [token for token in raw_given if token not in AUTHOR_PARTICLES]
    candidate = [token for token in candidate if token not in AUTHOR_PARTICLES]
    if not raw_given:
        return True
    candidate_index = 0
    for raw_token in raw_given:
        while candidate_index < len(candidate):
            candidate_token = candidate[candidate_index]
            candidate_index += 1
            if (
                candidate_token.startswith(raw_token)
                if len(raw_token) > 1
                else candidate_token.startswith(raw_token[:1])
            ):
                break
        else:
            return False
    return True


def resolve_author(raw_name, by_id, aliases, surnames):
    if raw_name in by_id:
        return raw_name, "already_id", []

    name_norm = normalized_text(raw_name)
    exact = aliases.get(name_norm, set())
    if len(exact) == 1:
        return next(iter(exact)), "exact_name", []
    if len(exact) > 1:
        return None, "ambiguous_exact_name", sorted(exact)

    raw_given, surname = author_parts(raw_name)
    candidates = surnames.get(surname, set())
    compatible = {
        author_id for author_id in candidates
        if given_names_compatible(
            raw_given,
            by_id[author_id].get("full_name") or by_id[author_id].get("name") or "",
        )
    }
    if len(compatible) == 1:
        return next(iter(compatible)), "initials_and_surname", []
    if len(compatible) > 1:
        return None, "ambiguous_initials_and_surname", sorted(compatible)
    return None, "author_not_found", sorted(candidates)


def build_work_title_index(works):
    index = defaultdict(set)
    for work in works:
        for title in [work.get("title")] + (work.get("alternative_titles") or []):
            if title:
                index[normalized_text(title)].add(work["id"])
    return index


def find_existing_work(record, works_by_id, title_index):
    direct_id = record.get("matched_work_id")
    if direct_id in works_by_id:
        return direct_id, "parser_title_match"

    candidates = set(title_index.get(normalized_text(record.get("title", "")), set()))
    if not candidates:
        year = record.get("year")
        author_ids = set(record.get("resolved_author_ids") or [])
        title_norm = normalized_text(record.get("title", ""))
        if not isinstance(year, int) or not author_ids or not title_norm:
            return None, None

        fuzzy = []
        for work_id, work in works_by_id.items():
            if work.get("year") != year:
                continue
            if not author_ids.intersection(work.get("authors") or []):
                continue
            score = SequenceMatcher(
                None,
                title_norm,
                normalized_text(work.get("title", "")),
            ).ratio()
            if score >= 0.82:
                fuzzy.append((score, work_id))

        fuzzy.sort(reverse=True)
        if fuzzy and (len(fuzzy) == 1 or fuzzy[0][0] - fuzzy[1][0] >= 0.05):
            return fuzzy[0][1], "structured_fuzzy_title"
        return None, None

    year = record.get("year")
    if isinstance(year, int):
        same_year = {
            work_id for work_id in candidates
            if works_by_id[work_id].get("year") in (None, year)
        }
        if not same_year:
            return None, None
        candidates = same_year

    author_ids = set(record.get("resolved_author_ids") or [])
    if author_ids:
        author_matches = {
            work_id for work_id in candidates
            if author_ids.intersection(works_by_id[work_id].get("authors") or [])
        }
        if not author_matches:
            return None, None
        candidates = author_matches

    if len(candidates) == 1:
        return next(iter(candidates)), "structured_exact_title"
    return None, None


def database_record(record):
    output = {
        "title": record.get("title"),
        "authors": record.get("resolved_author_ids") or [],
    }
    if record.get("year") is not None:
        output["year"] = record["year"]
    if record.get("type"):
        output["type"] = record["type"]
    field_map = {
        "journal": "journal", "volume": "volume", "number": "number",
        "pages": "pages", "location": "location", "publisher": "publisher",
        "booktitle": "booktitle", "series": "series",
        "additional_information": "notes",
    }
    for source_field, target_field in field_map.items():
        value = record.get(source_field)
        if value not in (None, "", []):
            output[target_field] = value
    return output


def validation_reasons(record):
    reasons = []
    if not record.get("title"):
        reasons.append("missing_title")
    if not record.get("resolved_author_ids"):
        reasons.append("missing_resolved_authors")
    if record.get("unresolved_author_names"):
        reasons.append("unresolved_or_ambiguous_authors")
    if record.get("type") not in VALID_TYPES:
        reasons.append("invalid_type")
    confidence = record.get("parse_confidence")
    if confidence is not None and confidence < 0.9:
        reasons.append("low_parse_confidence")
    title = record.get("title") or ""
    if len(title.strip()) < 10:
        reasons.append("suspiciously_short_title")
    if re.search(r"^review\s+of\s+\[?\d|[\[\]]", title, re.IGNORECASE):
        reasons.append("placeholder_or_broken_title")
    if re.search(r"\band\s*[a-z]$", title, re.IGNORECASE):
        reasons.append("possibly_ocr_damaged_title")
    raw_years = set(re.findall(r"\b(?:1[5-9]\d{2}|20\d{2})\b", record.get("raw_reference") or ""))
    if len(raw_years) > 1:
        reasons.append("multiple_reference_years")
    return reasons


def candidate_key(record):
    authors = record.get("resolved_author_ids") or [
        normalized_text(name) for name in record.get("authors") or []
    ]
    return (
        normalized_text(record.get("title", "")),
        record.get("year"),
        tuple(sorted(authors)),
    )


def richness(record):
    useful_fields = (
        "title", "authors", "year", "type", "journal", "volume", "number",
        "pages", "location", "publisher", "additional_information",
    )
    return sum(record.get(field) not in (None, "", []) for field in useful_fields)


def id_suffix(number):
    result = ""
    while True:
        number, remainder = divmod(number, 26)
        result = chr(ord("a") + remainder) + result
        if number == 0:
            return result
        number -= 1


def assign_ids(records, used_ids, authors_by_id):
    used_lower = {work_id.lower() for work_id in used_ids}
    for record in records:
        author = authors_by_id[record["authors"][0]]
        full_name = author.get("full_name") or author.get("name") or record["authors"][0]
        surname = author_parts(full_name)[1]
        stem = "".join(part.capitalize() for part in re.findall(r"[a-z0-9]+", surname))
        year_token = record.get("year") if isinstance(record.get("year"), int) else "Undated"
        base = f"{stem}{year_token}"
        suffix_number = 0
        while f"{base}{id_suffix(suffix_number)}".lower() in used_lower:
            suffix_number += 1
        record["id"] = f"{base}{id_suffix(suffix_number)}"
        used_lower.add(record["id"].lower())


def build_source_index(original_entries):
    result = defaultdict(set)
    for entry in original_entries:
        source = entry.get("source")
        for reference in entry.get("references") or []:
            raw = reference.get("reference") if isinstance(reference, dict) else None
            if source and raw:
                result[normalized_text(raw)].add(source)
    return result


def main():
    authors = load_json(AUTHORS_PATH)
    works = load_json(WORKS_PATH)
    authors_by_id, aliases, surnames = build_author_indexes(authors)
    works_by_id = {work["id"]: work for work in works}
    title_index = build_work_title_index(works)
    source_index = build_source_index(load_json(ORIGINAL_PATH))

    parsed_records = []
    for branch, path in PARSED_INPUTS:
        for record in load_json(path):
            record = dict(record)
            record["pipeline_branch"] = branch
            parsed_records.append(record)

    existing_matches = []
    unmatched = []
    for record in parsed_records:
        resolved_ids = []
        unresolved_names = []
        author_resolution = []
        for raw_name in record.get("authors") or []:
            author_id, method, candidates = resolve_author(
                raw_name, authors_by_id, aliases, surnames
            )
            author_resolution.append({
                "input": raw_name,
                "author_id": author_id,
                "method": method,
                "candidates": candidates,
            })
            if author_id:
                resolved_ids.append(author_id)
            else:
                unresolved_names.append(raw_name)

        record["resolved_author_ids"] = list(dict.fromkeys(resolved_ids))
        record["unresolved_author_names"] = unresolved_names
        record["author_resolution"] = author_resolution

        work_id, match_method = find_existing_work(record, works_by_id, title_index)
        if work_id:
            existing_matches.append({
                "matched_work_id": work_id,
                "match_method": match_method,
                "pipeline_branch": record["pipeline_branch"],
                "raw_reference": record.get("raw_reference"),
                "parsed_title": record.get("title"),
                "parsed_year": record.get("year"),
            })
        else:
            unmatched.append(record)

    best_by_key = {}
    duplicate_records = []
    for record in unmatched:
        key = candidate_key(record)
        previous = best_by_key.get(key)
        if previous is None:
            best_by_key[key] = record
            continue
        if richness(record) > richness(previous):
            kept, removed = record, previous
            best_by_key[key] = record
        else:
            kept, removed = previous, record
        duplicate_records.append({
            "title": removed.get("title"),
            "year": removed.get("year"),
            "kept_branch": kept.get("pipeline_branch"),
            "removed_branch": removed.get("pipeline_branch"),
            "kept_raw_reference": kept.get("raw_reference"),
            "removed_raw_reference": removed.get("raw_reference"),
        })

    ready_records = []
    review_records = []
    ready_audit = []
    for record in best_by_key.values():
        reasons = validation_reasons(record)
        raw_reference = record.get("raw_reference")
        sources = sorted(source_index.get(normalized_text(raw_reference or ""), set()))
        if reasons:
            review_records.append({
                "review_reasons": reasons,
                "pipeline_branch": record["pipeline_branch"],
                "raw_reference": raw_reference,
                "source_articles": sources,
                "parsed_record": database_record(record),
                "author_resolution": record["author_resolution"],
                "parse_strategy": record.get("parse_strategy"),
                "parse_confidence": record.get("parse_confidence"),
            })
            continue

        output = database_record(record)
        ready_records.append(output)
        ready_audit.append({
            "record": output,
            "pipeline_branch": record["pipeline_branch"],
            "raw_reference": raw_reference,
            "source_articles": sources,
            "author_resolution": record["author_resolution"],
            "parse_strategy": record.get("parse_strategy"),
            "parse_confidence": record.get("parse_confidence"),
        })

    parsed_raw_keys = {
        normalized_text(record.get("raw_reference") or "")
        for record in parsed_records
        if record.get("raw_reference")
    }
    unparsed_inputs = []
    for branch, input_path in (
        ("all_caps", ALL_CAPS_INPUT_PATH),
        ("with_authors", WITH_AUTHORS_INPUT_PATH),
    ):
        for raw_reference in load_json(input_path):
            if normalized_text(raw_reference) not in parsed_raw_keys:
                unparsed_inputs.append((branch, raw_reference, "base_parser_rejected"))

    for item in load_json(NO_AUTHOR_UNRESOLVED_PATH):
        unparsed_inputs.append((
            "no_authors",
            item.get("raw_reference"),
            item.get("category") or "unresolved",
        ))

    for branch, raw_reference, category in unparsed_inputs:
        sources = sorted(source_index.get(normalized_text(raw_reference or ""), set()))
        review_records.append({
            "review_reasons": ["unparsed_reference"],
            "pipeline_branch": branch,
            "raw_reference": raw_reference,
            "source_articles": sources,
            "unparsed_category": category,
            "parsed_record": None,
            "author_resolution": [],
            "parse_strategy": None,
            "parse_confidence": 0.0,
        })

    invalid_or_contextual = []
    for path in (NO_AUTHOR_CONTEXTUAL_PATH, NO_AUTHOR_FRAGMENTS_PATH):
        for item in load_json(path):
            item = dict(item)
            raw_reference = item.get("raw_reference")
            item["source_articles"] = sorted(
                source_index.get(normalized_text(raw_reference or ""), set())
            )
            invalid_or_contextual.append(item)

    assign_ids(ready_records, works_by_id, authors_by_id)
    for audit, record in zip(ready_audit, ready_records):
        audit["record"] = record

    outputs = (
        (READY_PATH, ready_records),
        (REVIEW_PATH, review_records),
        (EXISTING_PATH, existing_matches),
        (DUPLICATES_PATH, duplicate_records),
        (AUDIT_PATH, ready_audit),
        (INVALID_CONTEXTUAL_PATH, invalid_or_contextual),
    )
    for path, value in outputs:
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Parsed input records: {len(parsed_records)}")
    print(f"Matched existing works: {len(existing_matches)}")
    print(f"Parsed duplicates removed: {len(duplicate_records)}")
    print(f"Ready to add after review: {len(ready_records)}")
    print(f"Needing review: {len(review_records)}")
    print(f"Invalid or contextual: {len(invalid_or_contextual)}")
    print(READY_PATH)
    print(REVIEW_PATH)


if __name__ == "__main__":
    main()
