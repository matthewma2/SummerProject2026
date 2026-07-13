#!/usr/bin/env python3
"""Classify and parse jsl_citations_data/4b_no_authors.json.

This stage handles the references that did not have an obvious leading author
in earlier passes. It first tries to recover missed author prefixes, then tries
title-first matching against works.json, and finally separates contextual
fragments from still-unresolved strings.
"""

import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path


BASE_PARSER_PATH = Path("jsl_citations_pipeline/3_parsing_unresolved_works.py")
AUTHOR_HELPERS_PATH = Path("jsl_citations_pipeline/6_parse_4a_with_authors.py")
INPUT_PATH = Path("jsl_citations_data/4b_no_authors.json")
WORKS_PATH = Path("databases/works.json")

PARSED_PATH = Path("jsl_citations_data/4b_parsed.json")
CLASSIFIED_PATH = Path("jsl_citations_data/4b_classified.json")
CONTEXTUAL_PATH = Path("jsl_citations_data/4b_contextual_references.json")
FRAGMENTS_PATH = Path("jsl_citations_data/4b_fragments.json")
UNRESOLVED_PATH = Path("jsl_citations_data/4b_unresolved_after_parse.json")
ERRORS_PATH = Path("jsl_citations_data/4b_parse_errors.txt")


def load_definitions(path, stop_marker=None):
    source = path.read_text(encoding="utf-8")
    if stop_marker:
        source = source.split(stop_marker, 1)[0]
    namespace = {"__name__": f"loaded_{path.stem}"}
    exec(compile(source, str(path), "exec"), namespace)
    return namespace


def load_base_parser():
    namespace = load_definitions(BASE_PARSER_PATH, "# 9. RUN ON ALL ENTRIES")
    namespace["query_crossref"] = lambda *args, **kwargs: None
    namespace["query_open_library"] = lambda *args, **kwargs: None
    return namespace


def load_author_helpers():
    return load_definitions(AUTHOR_HELPERS_PATH, "\nif __name__ == \"__main__\":")


def strip_continuation_marker(text):
    return re.sub(r"^\s*[—-]\s*", "", text).strip()


def normalize_for_match(text, norm):
    text = strip_continuation_marker(text)
    text = text.replace("orn", "on")
    text = text.replace("Mathe- matical", "Mathematical")
    text = text.replace("mathe- matical", "mathematical")
    text = text.replace("Ameri- can", "American")
    text = text.replace("JOUR- NAL", "JOURNAL")
    text = text.replace("vof.", "vol.")
    text = re.sub(r"\bA\s+n\s+", "An ", text)
    text = re.sub(r"\bewfoundation8for\b", "New foundations for", text, flags=re.IGNORECASE)
    text = re.sub(r"\bewfoundation8\b", "New foundations", text, flags=re.IGNORECASE)
    text = re.sub(r"\bn\s+Cantor", "On Cantor", text)
    text = re.sub(r"\ber\s+Wahrheitsbegriff", "Der Wahrheitsbegriff", text)
    return norm(text)


def build_work_terms(works, norm):
    stopwords = {
        "a", "an", "the", "on", "of", "in", "to", "for", "der", "die", "das",
        "le", "la", "les", "sur", "uber", "ueber", "zur", "zum",
    }
    terms = []
    for work in works:
        titles = [work.get("title")] + (work.get("alternative_titles") or [])
        for title in titles:
            if not title:
                continue
            title_norm = norm(title)
            token_count = len(title_norm.split())
            if token_count < 3:
                continue
            key_tokens = [tok for tok in title_norm.split() if tok not in stopwords]
            terms.append({
                "term": title,
                "term_norm": title_norm,
                "token_count": token_count,
                "match_key": key_tokens[0] if key_tokens else title_norm.split()[0],
                "work": work,
            })
    return sorted(terms, key=lambda item: len(item["term_norm"]), reverse=True)


def prefix_similarity(reference_norm, term_norm):
    ref_tokens = reference_norm.split()
    term_tokens = term_norm.split()
    if not ref_tokens or not term_tokens:
        return 0.0

    widths = {len(term_tokens), len(term_tokens) + 1, max(1, len(term_tokens) - 1)}
    best = 0.0
    for width in widths:
        prefix = " ".join(ref_tokens[:width])
        best = max(best, SequenceMatcher(None, prefix, term_norm).ratio())
    return best


def extract_reference_year(raw):
    years = [
        int(match.group(0))
        for match in re.finditer(r"\b(?:1[5-9]\d{2}|20\d{2})\b", raw)
    ]
    return years[0] if years else None


def find_title_first_work(raw, work_terms, norm):
    ref_norm = normalize_for_match(raw, norm)
    if not ref_norm:
        return None
    ref_tokens = ref_norm.split()
    ref_start = set(ref_tokens[:12])
    ref_year = extract_reference_year(raw)

    best = None
    for item in work_terms:
        term_norm = item["term_norm"]
        term_tokens = item["token_count"]
        score = 0.0
        method = None

        if ref_norm.startswith(term_norm):
            score = 1.0
            method = "title_prefix"
        elif term_norm in ref_norm[: max(80, len(term_norm) + 30)]:
            score = 0.94
            method = "title_near_start"
        elif term_tokens >= 4 and item["match_key"] in ref_start:
            score = prefix_similarity(ref_norm, term_norm)
            if score >= 0.86:
                method = "title_fuzzy_prefix"

        if not method:
            continue

        work_year = item["work"].get("year")
        if (
            method == "title_fuzzy_prefix"
            and ref_year
            and isinstance(work_year, int)
            and abs(work_year - ref_year) > 3
        ):
            continue

        if best is None or score > best["score"] or (
            score == best["score"] and item["token_count"] > best["term"]["token_count"]
        ):
            best = {"term": item, "score": round(score, 3), "method": method}

    return best


def classify_unparsed(raw):
    text = raw.strip()
    low = text.lower()

    if re.match(r"^(?:mathe-?\s*matical reviews?|zentralblatt)\b", low):
        return "review_index", 0.98
    if re.match(r"^(?:vol\.|bd\.|pp?\.|s\.|p\.)\s", low):
        return "fragment", 0.95
    if re.match(r"^(?:this journal|the journal of symbolic logic),?\s+vol", low):
        return "fragment", 0.95
    if re.match(r"^(?:duke mathematical journal|fundamenta mathematicae|indagationes mathematicae|annals of mathematics|bulletin|proceedings|transactions)\b", low):
        return "fragment", 0.88
    if re.search(r"\b(?:ibid|idem|to the same|same)\b", low):
        return "contextual", 0.9
    if re.match(r"^(?:reprinted|revised|second|third)\s+edition\b", low):
        return "contextual", 0.9
    if re.match(r"^(?:in|chapter|part|parts?)\b", low):
        return "contextual", 0.75
    if re.search(r"\b(?:my paper|author's|authors'|present authors|the authors|their|his|her)\b", low):
        return "contextual", 0.82
    if re.search(r"\b(?:presented|paper was read|prepared under|personal communication|has shown|has announced)\b", low):
        return "contextual", 0.86
    if len(text) < 45 and not re.search(r"\b\d{4}\b", text):
        return "fragment", 0.7
    return "unresolved", 0.0


def pre_parse_bucket(raw):
    text = raw.strip()
    low = text.lower()

    if re.match(r"^(?:mathe-?\s*matical reviews?|zentralblatt)\b", low):
        return "review_index", 0.98
    if re.match(r"^(?:vol\.|bd\.|pp?\.|s\.|p\.)\s", low):
        return "fragment", 0.95
    if re.match(r"^(?:this journal|the journal of symbolic logic),?\s+vol", low):
        return "fragment", 0.95
    if re.match(r"^(?:reprinted|revised|second|third)\s+edition\b", low):
        return "contextual", 0.92
    if re.search(r"\b(?:presented|paper was read|prepared under|under the title|personal communication|has shown|has announced)\b", low):
        return "contextual", 0.9
    if re.search(r"\b(?:my paper|author's|authors'|present authors|the authors|their|his doctoral dissertation|miss james's doctoral dissertation)\b", low):
        return "contextual", 0.86
    return None, 0.0


def authors_from_by_or_with(raw, consume_author_prefix):
    contributors = []
    for marker in (r"\bby\s+", r"\bWith\s+"):
        for match in re.finditer(marker, raw):
            authors, _ = consume_author_prefix(raw[match.end():])
            if authors:
                contributors.extend(authors)
                break
    return contributors


TITLE_LEAD_WORDS = {
    "a", "an", "the", "on", "in", "from", "studies", "introduction",
    "grundlagen", "grundzuge", "mathematical", "logic", "truth",
    "probability", "constructivity", "polish", "proceedings", "bulletin",
    "annals", "fundamenta", "duke", "indagationes", "reprinted",
    "element", "computability", "implication", "part", "sequences",
    "abstract", "modalities", "vgl", "mathematische", "past", "improved",
    "neue", "zur", "die",
}


def plausible_recovered_authors(authors):
    if not authors:
        return False

    if authors[0].lstrip().startswith(("—", "-")):
        return False

    first_norm = re.sub(r"[^a-z]+", " ", authors[0].lower()).strip()
    first_word = first_norm.split()[0] if first_norm else ""
    if first_word in TITLE_LEAD_WORDS:
        return False
    if len(first_word) == 1 and len(first_norm.split()) == 1:
        return False

    for author in authors:
        author_low = author.lower()
        if "this journal" in author_low or " vol" in author_low or "journal" in author_low:
            return False
        clean = re.sub(r"\([^)]*\)", "", author).strip()
        words = [
            part for part in re.split(r"\s+", clean)
            if part and part.lower() not in {"jr", "sr", "ed"}
        ]
        if len(words) > 5:
            return False
        if any(word.lower() in {"journal", "mathematics", "logic", "calculus", "theory"} for word in words[:2]):
            return False

    return True


def plausible_author_remainder(rest):
    rest = rest.strip(" ,.;")
    if not rest:
        return False
    if re.match(r"^(?:this\s+journal|ibid|vol\.?|v[0o]l\.?|bd\.?|no\.?|pp?\.|s\.)\b", rest, re.IGNORECASE):
        return False
    if len(rest) < 8:
        return False
    return True


def generic_author_prefix(raw, split_authors):
    token = r"(?:[A-ZÀ-ÖØ-Þ0]\.|[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿĀ-ſ'’-]+)"
    name = rf"{token}(?:\s+{token}){{0,4}}"
    pattern = re.compile(
        rf"^({name}(?:\s+and\s+{name}){{0,3}})[\.,]\s+(.+)$"
    )
    match = pattern.match(raw.strip())
    if not match:
        return [], raw

    authors = split_authors(match.group(1))
    rest = match.group(2).strip()
    if not plausible_recovered_authors(authors) or not plausible_author_remainder(rest):
        return [], raw
    return authors, rest


def parse_with_recovered_author(raw, base, author_helpers):
    consume_author_prefix = author_helpers["consume_author_prefix"]
    authors, rest = consume_author_prefix(raw)
    if not plausible_recovered_authors(authors) or not plausible_author_remainder(rest):
        authors, rest = generic_author_prefix(raw, author_helpers["split_authors"])
    if not authors:
        return None

    def extract_authors_override(_text):
        return authors, rest

    old_extract = base["extract_authors"]
    base["extract_authors"] = extract_authors_override
    try:
        parsed, reason = base["parse_one"](raw)
    finally:
        base["extract_authors"] = old_extract

    if parsed is None:
        return None
    parsed["raw_reference"] = raw
    parsed["parse_strategy"] = "missed_author_prefix"
    parsed["parse_confidence"] = 0.86
    return parsed


def parse_title_first(raw, base, title_match):
    work = title_match["term"]["work"]
    parsed, reason = base["parse_one"](raw)

    if parsed is None:
        parsed = {
            "title": work.get("title") or title_match["term"]["term"],
            "authors": [],
            "year": None,
            "type": work.get("type") or "work",
        }

    parsed["raw_reference"] = raw
    parsed["parse_strategy"] = title_match["method"]
    parsed["parse_confidence"] = title_match["score"]
    parsed["matched_work_id"] = work.get("id")
    parsed["matched_work_title"] = work.get("title")
    parsed["matched_work_authors"] = work.get("authors") or []
    parsed["matched_term"] = title_match["term"]["term"]

    if not parsed.get("authors") and work.get("authors"):
        parsed["authors"] = work.get("authors")
    if not parsed.get("year") and work.get("year") is not None:
        parsed["year"] = work.get("year")
    if not parsed.get("type") and work.get("type"):
        parsed["type"] = work.get("type")

    return parsed


def main():
    base = load_base_parser()
    author_helpers = load_author_helpers()
    norm = author_helpers["norm"]
    works = json.loads(WORKS_PATH.read_text(encoding="utf-8"))
    work_terms = build_work_terms(works, norm)
    refs = json.loads(INPUT_PATH.read_text(encoding="utf-8"))

    parsed = []
    classified = []
    contextual = []
    fragments = []
    unresolved = []
    errors = []

    print(f"Processing {len(refs)} reference strings...", file=sys.stderr)

    for i, raw in enumerate(refs):
        if i % 100 == 0:
            print(f"  {i}/{len(refs)}", file=sys.stderr)

        record = {
            "raw_reference": raw,
            "category": None,
            "confidence": 0.0,
            "parsed": False,
        }

        try:
            entry = parse_with_recovered_author(raw, base, author_helpers)
            if entry:
                entry["additional_contributors"] = authors_from_by_or_with(
                    raw,
                    author_helpers["consume_author_prefix"],
                )
                parsed.append(entry)
                record.update({
                    "category": "missed_author",
                    "confidence": entry["parse_confidence"],
                    "parsed": True,
                })
                classified.append(record)
                continue

            pre_category, pre_confidence = pre_parse_bucket(raw)
            if pre_category:
                record.update({"category": pre_category, "confidence": pre_confidence})
                classified.append(record)
                bucket_record = {
                    "raw_reference": raw,
                    "category": pre_category,
                    "confidence": pre_confidence,
                }
                if pre_category == "contextual":
                    contextual.append(bucket_record)
                else:
                    fragments.append(bucket_record)
                continue

            title_match = find_title_first_work(raw, work_terms, norm)
            if title_match:
                entry = parse_title_first(raw, base, title_match)
                entry["additional_contributors"] = authors_from_by_or_with(
                    raw,
                    author_helpers["consume_author_prefix"],
                )
                parsed.append(entry)
                record.update({
                    "category": "title_first",
                    "confidence": entry["parse_confidence"],
                    "parsed": True,
                    "matched_work_id": entry.get("matched_work_id"),
                    "matched_work_title": entry.get("matched_work_title"),
                })
                classified.append(record)
                continue

            category, confidence = classify_unparsed(raw)
            record.update({"category": category, "confidence": confidence})
            classified.append(record)

            unresolved_record = {
                "raw_reference": raw,
                "category": category,
                "confidence": confidence,
            }
            if category == "contextual":
                contextual.append(unresolved_record)
            elif category in {"fragment", "review_index"}:
                fragments.append(unresolved_record)
            else:
                unresolved.append(unresolved_record)

        except Exception as exc:
            errors.append((raw, str(exc)))
            record.update({"category": "error", "confidence": 0.0, "error": str(exc)})
            classified.append(record)
            unresolved.append({
                "raw_reference": raw,
                "category": "error",
                "confidence": 0.0,
                "error": str(exc),
            })

    PARSED_PATH.write_text(json.dumps(parsed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    CLASSIFIED_PATH.write_text(json.dumps(classified, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    CONTEXTUAL_PATH.write_text(json.dumps(contextual, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    FRAGMENTS_PATH.write_text(json.dumps(fragments, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    UNRESOLVED_PATH.write_text(json.dumps(unresolved, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if errors:
        ERRORS_PATH.write_text(
            "".join(f"ERROR: {err}\n  RAW: {raw}\n\n" for raw, err in errors),
            encoding="utf-8",
        )

    print(
        "Done. "
        f"Parsed: {len(parsed)}, "
        f"Contextual: {len(contextual)}, "
        f"Fragments: {len(fragments)}, "
        f"Unresolved: {len(unresolved)}, "
        f"Errors: {len(errors)}",
        file=sys.stderr,
    )
    print(f"Output written to {PARSED_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
