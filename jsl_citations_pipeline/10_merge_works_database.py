#!/usr/bin/env python3
"""Safely merge reviewed JSL work candidates into a new works database."""

import json
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKS_PATH = PROJECT_ROOT / "databases" / "works.json"
CANDIDATES_PATH = PROJECT_ROOT / "jsl_citations_data" / "10a_works_ready_to_add.json"
OUTPUT_PATH = PROJECT_ROOT / "jsl_citations_data" / "11_merged_database.json"
LOG_PATH = PROJECT_ROOT / "jsl_citations_pipeline_logs" / "10_merge_works_database_log.json"

SPECIAL = str.maketrans({
    "Ł": "L", "ł": "l", "Ø": "O", "ø": "o", "Đ": "D", "đ": "d",
    "Æ": "Ae", "æ": "ae", "Œ": "Oe", "œ": "oe", "0": "O",
})


def normalized_text(value):
    value = str(value or "").translate(SPECIAL)
    value = "".join(
        char for char in unicodedata.normalize("NFD", value)
        if unicodedata.category(char) != "Mn"
    )
    value = re.sub(r"(\w)-\s+(\w)", r"\1\2", value)
    value = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", value)


def load_list(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return value


def author_sets_compatible(left, right):
    left = set(left or [])
    right = set(right or [])
    return bool(left and right) and (left <= right or right <= left)


def years_compatible(left, right):
    return left is None or right is None or left == right


def metadata_score(candidate, work):
    score = 0
    for field in ("journal", "volume", "number", "pages", "location", "publisher"):
        left = normalized_text(candidate.get(field))
        right = normalized_text(work.get(field))
        if left and right and left == right:
            score += 1
    return score


def venue_conflicts(candidate, work):
    left_journal = normalized_text(candidate.get("journal"))
    right_journal = normalized_text(work.get("journal"))
    if left_journal and right_journal and left_journal != right_journal:
        return True

    left_volume = normalized_text(candidate.get("volume"))
    right_volume = normalized_text(work.get("volume"))
    if (
        left_journal and left_journal == right_journal
        and left_volume and right_volume and left_volume != right_volume
    ):
        return True
    return False


def title_without_trailing_metadata(record):
    """Remove only trailing title tokens duplicated by structured metadata."""
    title_tokens = normalized_text(record.get("title")).split()
    noise_tokens = set()
    for field in ("location", "publisher"):
        noise_tokens.update(normalized_text(record.get(field)).split())
    if record.get("year") is not None:
        noise_tokens.update(normalized_text(record["year"]).split())

    while len(title_tokens) > 2 and title_tokens[-1] in noise_tokens:
        title_tokens.pop()
    return " ".join(title_tokens)


def choose_duplicate(candidate, works):
    """Return (match, method, alternatives) for a probable duplicate work."""
    candidate_title = normalized_text(candidate.get("title"))
    if not candidate_title or not candidate.get("authors"):
        return None, None, []

    compatible = [
        work for work in works
        if author_sets_compatible(candidate.get("authors"), work.get("authors"))
        and years_compatible(candidate.get("year"), work.get("year"))
        and not venue_conflicts(candidate, work)
    ]

    exact = [work for work in compatible if normalized_text(work.get("title")) == candidate_title]
    if exact:
        ranked = sorted(
            exact,
            key=lambda work: (
                metadata_score(candidate, work),
                set(candidate.get("authors") or []) == set(work.get("authors") or []),
                candidate.get("year") is not None and candidate.get("year") == work.get("year"),
            ),
            reverse=True,
        )
        alternatives = [work["id"] for work in ranked]
        if len(ranked) == 1 or metadata_score(candidate, ranked[0]) > metadata_score(candidate, ranked[1]):
            return ranked[0], "exact_title_author", alternatives
        return None, "ambiguous_exact_duplicate", alternatives

    # Parsers sometimes leave a location or year at the end of a title. Treat
    # this as an exact duplicate only when removing structured trailing metadata
    # makes the titles equal and the author/year/venue checks above already agree.
    candidate_core_title = title_without_trailing_metadata(candidate)
    core_exact = [
        work for work in compatible
        if candidate_core_title
        and candidate_core_title == title_without_trailing_metadata(work)
    ]
    if core_exact:
        ranked = sorted(
            core_exact,
            key=lambda work: (
                metadata_score(candidate, work),
                set(candidate.get("authors") or []) == set(work.get("authors") or []),
                candidate.get("year") is not None and candidate.get("year") == work.get("year"),
            ),
            reverse=True,
        )
        alternatives = [work["id"] for work in ranked]
        if len(ranked) == 1 or metadata_score(candidate, ranked[0]) > metadata_score(candidate, ranked[1]):
            return ranked[0], "exact_title_after_trailing_metadata", alternatives
        return None, "ambiguous_metadata_trimmed_duplicate", alternatives

    if len(candidate_title.split()) < 3:
        return None, None, []

    fuzzy = []
    candidate_authors = set(candidate.get("authors") or [])
    for work in compatible:
        work_title = normalized_text(work.get("title"))
        if len(work_title.split()) < 3:
            continue
        similarity = SequenceMatcher(None, candidate_title, work_title).ratio()
        metadata = metadata_score(candidate, work)
        same_authors = candidate_authors == set(work.get("authors") or [])
        same_year = (
            candidate.get("year") is not None
            and candidate.get("year") == work.get("year")
        )
        strong_context = same_authors and same_year
        if similarity >= 0.96 and strong_context:
            fuzzy.append((similarity, metadata, work))
        elif similarity >= 0.92 and strong_context and metadata:
            fuzzy.append((similarity, metadata, work))

    fuzzy.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if not fuzzy:
        return None, None, []
    alternatives = [item[2]["id"] for item in fuzzy]
    if len(fuzzy) == 1 or fuzzy[0][0] - fuzzy[1][0] >= 0.03:
        return fuzzy[0][2], "fuzzy_title_author_year", alternatives
    return None, "ambiguous_fuzzy_duplicate", alternatives


def suffix_to_number(suffix):
    number = 0
    for char in suffix.lower():
        number = number * 26 + ord(char) - ord("a") + 1
    return number - 1


def number_to_suffix(number):
    result = ""
    number += 1
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(ord("a") + remainder) + result
    return result


def unique_id(proposed_id, used_ids):
    if proposed_id.lower() not in used_ids:
        return proposed_id

    match = re.match(r"^(.*(?:\d|Undated))([A-Za-z]+)$", proposed_id)
    if match:
        stem = match.group(1)
        number = suffix_to_number(match.group(2)) + 1
    else:
        stem = proposed_id
        number = 0

    while f"{stem}{number_to_suffix(number)}".lower() in used_ids:
        number += 1
    return f"{stem}{number_to_suffix(number)}"


def preexisting_same_identity_groups(works):
    groups = defaultdict(list)
    for work in works:
        key = (
            normalized_text(work.get("title")),
            tuple(sorted(work.get("authors") or [])),
            work.get("year"),
        )
        groups[key].append(work)

    output = []
    for (title, authors, year), records in groups.items():
        if len(records) < 2:
            continue
        output.append({
            "normalized_title": title,
            "authors": list(authors),
            "year": year,
            "work_ids": [record["id"] for record in records],
            "metadata": [
                {
                    key: record.get(key)
                    for key in ("id", "type", "journal", "volume", "number", "pages", "location")
                    if record.get(key) is not None
                }
                for record in records
            ],
        })
    return output


def main():
    works = load_list(WORKS_PATH)
    candidates = load_list(CANDIDATES_PATH)

    existing_ids = [work.get("id") for work in works]
    if any(not isinstance(work_id, str) or not work_id for work_id in existing_ids):
        raise ValueError("Every existing work must have a non-empty string ID")
    if len({work_id.lower() for work_id in existing_ids}) != len(existing_ids):
        raise ValueError("works.json already contains duplicate IDs")

    merged = [dict(work) for work in works]
    used_ids = {work_id.lower() for work_id in existing_ids}
    duplicate_candidates = []
    ambiguous_duplicates = []
    id_adjustments = []
    rejected_candidates = []
    added_ids = []

    for input_index, raw_candidate in enumerate(candidates):
        if not isinstance(raw_candidate, dict):
            rejected_candidates.append({"input_index": input_index, "reason": "not_an_object"})
            continue

        candidate = dict(raw_candidate)
        if not candidate.get("title") or not candidate.get("authors"):
            rejected_candidates.append({
                "input_index": input_index,
                "reason": "missing_title_or_authors",
                "candidate": candidate,
            })
            continue

        duplicate, method, alternatives = choose_duplicate(candidate, merged)
        if duplicate:
            duplicate_candidates.append({
                "input_index": input_index,
                "candidate_id": candidate.get("id"),
                "candidate_title": candidate.get("title"),
                "matched_work_id": duplicate["id"],
                "match_method": method,
                "alternative_matches": alternatives,
            })
            continue
        if method and method.startswith("ambiguous_"):
            ambiguous_duplicates.append({
                "input_index": input_index,
                "candidate_id": candidate.get("id"),
                "candidate_title": candidate.get("title"),
                "reason": method,
                "possible_work_ids": alternatives,
            })
            continue

        proposed_id = candidate.get("id")
        if not isinstance(proposed_id, str) or not proposed_id:
            rejected_candidates.append({
                "input_index": input_index,
                "reason": "missing_id",
                "candidate": candidate,
            })
            continue

        adjusted_id = unique_id(proposed_id, used_ids)
        if adjusted_id != proposed_id:
            id_adjustments.append({
                "input_index": input_index,
                "original_id": proposed_id,
                "adjusted_id": adjusted_id,
                "title": candidate.get("title"),
            })
            candidate["id"] = adjusted_id

        used_ids.add(candidate["id"].lower())
        merged.append(candidate)
        added_ids.append(candidate["id"])

    output_ids = [work["id"].lower() for work in merged]
    if len(output_ids) != len(set(output_ids)):
        raise RuntimeError("Refusing to write merged database with duplicate IDs")

    log = {
        "works_input": str(WORKS_PATH),
        "candidates_input": str(CANDIDATES_PATH),
        "merged_output": str(OUTPUT_PATH),
        "existing_works": len(works),
        "input_candidates": len(candidates),
        "candidates_added": len(added_ids),
        "duplicate_candidates_skipped": len(duplicate_candidates),
        "ambiguous_duplicates_skipped": len(ambiguous_duplicates),
        "rejected_candidates": len(rejected_candidates),
        "id_adjustments": len(id_adjustments),
        "merged_works": len(merged),
        "added_ids": added_ids,
        "duplicate_candidate_details": duplicate_candidates,
        "ambiguous_duplicate_details": ambiguous_duplicates,
        "id_adjustment_details": id_adjustments,
        "rejected_candidate_details": rejected_candidates,
        "preexisting_same_title_author_year_groups": preexisting_same_identity_groups(works),
    }

    OUTPUT_PATH.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    LOG_PATH.write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Existing works: {len(works)}")
    print(f"Candidate works: {len(candidates)}")
    print(f"Added: {len(added_ids)}")
    print(f"Duplicate candidates skipped: {len(duplicate_candidates)}")
    print(f"Ambiguous duplicates skipped: {len(ambiguous_duplicates)}")
    print(f"Rejected candidates: {len(rejected_candidates)}")
    print(f"IDs adjusted: {len(id_adjustments)}")
    print(f"Merged works: {len(merged)}")
    print(OUTPUT_PATH)
    print(LOG_PATH)


if __name__ == "__main__":
    main()
