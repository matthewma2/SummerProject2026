#!/usr/bin/env python3
"""Resolve title-less ``this JOURNAL`` references via exact Crossref metadata.

This stage is deliberately isolated from the works database. It downloads and
caches JSL metadata by publication year, then writes an audit map for stage 11.
Only a unique Crossref record with the exact volume, year, and page range can
be accepted, and that record must map unambiguously to the merged database.
"""

import argparse
import html
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "jsl_citations_data"
LOG_DIR = PROJECT_ROOT / "jsl_citations_pipeline_logs"

INPUT_PATH = DATA_DIR / "2_jsl_citations_cleaned.json"
WORKS_PATH = DATA_DIR / "11_merged_database.json"
CACHE_PATH = LOG_DIR / "10b_crossref_jsl_metadata_cache.json"
OUTPUT_PATH = LOG_DIR / "10b_jsl_journal_metadata_resolution.json"

JSL_ISSN = "0022-4812"
CROSSREF_ENDPOINT = f"https://api.crossref.org/journals/{JSL_ISSN}/works"
RESOLUTION_METHOD = "crossref_jsl_exact_volume_year_pages"

# Intentionally limited to title-less references with a complete page range.
# Single-page citations may point inside an article and are therefore excluded.
REFERENCE_PATTERN = re.compile(
    r"^\s*this\s+journal\s*,?\s*"
    r"(?:(?:v(?:ol|o1)\.?\s*)?)(?P<volume>\d+)"
    r"(?:\s*,?\s*(?:no\.?|number)\s*(?P<issue>\d+))?"
    r"\s*,?\s*\((?P<year>\d{4})\)"
    r"\s*,?\s*pp\s*[.,;]?\s*"
    r"(?P<first>[a-z]?\d+|[ivxlcdm]+)\s*[-–—]\s*"
    r"(?P<last>[a-z]?\d+|[ivxlcdm]+)\s*[.)]*\s*$",
    re.IGNORECASE,
)


def load_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def normalize_text(value):
    value = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    value = "".join(
        char for char in unicodedata.normalize("NFD", value)
        if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def normalize_page(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower()) or None


def page_range(value):
    parts = re.split(r"\s*[-–—]\s*", str(value or "").strip(), maxsplit=1)
    if len(parts) != 2:
        return None
    first, last = map(normalize_page, parts)
    return (first, last) if first and last else None


def parse_reference(raw_reference):
    match = REFERENCE_PATTERN.match(raw_reference)
    if not match:
        return None
    return {
        "volume": str(int(match.group("volume"))),
        "issue": str(int(match.group("issue"))) if match.group("issue") else None,
        "year": int(match.group("year")),
        "first_page": normalize_page(match.group("first")),
        "last_page": normalize_page(match.group("last")),
    }


def extract_year(item):
    for field in ("published", "published-print", "issued"):
        parts = ((item.get(field) or {}).get("date-parts") or [])
        if parts and parts[0]:
            try:
                return int(parts[0][0])
            except (TypeError, ValueError):
                pass
    return None


def normalized_doi(value):
    value = str(value or "").strip().lower()
    match = re.search(r"10\.\d{4,9}/[^\s?#]+", value)
    return match.group(0).rstrip("/.,;)") if match else None


def compact_crossref_item(item):
    titles = item.get("title") or []
    return {
        "doi": normalized_doi(item.get("DOI")),
        "title": html.unescape(re.sub(r"<[^>]+>", "", titles[0])) if titles else None,
        "authors": [
            " ".join(part for part in (author.get("given"), author.get("family")) if part)
            for author in item.get("author") or []
        ],
        "year": extract_year(item),
        "volume": str(item.get("volume")) if item.get("volume") is not None else None,
        "issue": str(item.get("issue")) if item.get("issue") is not None else None,
        "pages": item.get("page"),
        "url": item.get("URL"),
    }


def fetch_crossref_year(year, mailto=None, attempts=3):
    params = {
        "filter": f"from-pub-date:{year}-01-01,until-pub-date:{year}-12-31",
        "rows": "1000",
        "select": "DOI,title,author,published,published-print,issued,volume,issue,page,URL",
    }
    if mailto:
        params["mailto"] = mailto
    url = f"{CROSSREF_ENDPOINT}?{urlencode(params)}"
    request = Request(
        url,
        headers={"User-Agent": "JSL-citation-pipeline/1.0 (bibliographic metadata research)"},
    )
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=45) as response:
                payload = json.load(response)
            message = payload.get("message") or {}
            total = int(message.get("total-results") or 0)
            items = message.get("items") or []
            if total > len(items):
                raise RuntimeError(
                    f"Crossref returned {len(items)} of {total} records for {year}; "
                    "refusing to use an incomplete year"
                )
            return [compact_crossref_item(item) for item in items], url
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            if attempt == attempts:
                raise RuntimeError(f"Crossref request failed for {year}: {error}") from error
            time.sleep(attempt * 2)
    raise AssertionError("unreachable")


def collect_targets(citations):
    references = {
        ref.get("reference")
        for entry in citations
        for ref in entry.get("references", [])
        if isinstance(ref, dict) and ref.get("reference")
    }
    return {
        raw_reference: parsed
        for raw_reference in sorted(references)
        if (parsed := parse_reference(raw_reference)) is not None
    }


def build_work_indexes(works):
    by_doi = {}
    by_title = {}
    for work in works:
        doi = normalized_doi(work.get("doi")) or normalized_doi(work.get("url"))
        if doi:
            by_doi.setdefault(doi, []).append(work)
        title = normalize_text(work.get("title"))
        if title:
            key = (title, work.get("year"), str(work.get("volume") or ""))
            by_title.setdefault(key, []).append(work)
    return by_doi, by_title


def map_external_work(item, by_doi, by_title):
    doi = item.get("doi")
    if doi and len(by_doi.get(doi, [])) == 1:
        return by_doi[doi][0], "doi"
    if doi and len(by_doi.get(doi, [])) > 1:
        return None, "ambiguous_local_doi"

    key = (normalize_text(item.get("title")), item.get("year"), item.get("volume") or "")
    title_matches = by_title.get(key, [])
    if len(title_matches) == 1:
        return title_matches[0], "exact_title_year_volume"
    if len(title_matches) > 1:
        return None, "ambiguous_local_title"
    return None, "no_local_work"


def resolve_target(parsed, items, by_doi, by_title):
    candidates = []
    wanted_pages = (parsed["first_page"], parsed["last_page"])
    for item in items:
        if item.get("year") != parsed["year"]:
            continue
        if str(item.get("volume") or "") != parsed["volume"]:
            continue
        if page_range(item.get("pages")) != wanted_pages:
            continue
        if parsed.get("issue") and str(item.get("issue") or "") != parsed["issue"]:
            continue
        candidates.append(item)

    # Crossref occasionally exposes duplicate representations of one DOI.
    unique_candidates = {}
    for item in candidates:
        identity = item.get("doi") or (
            normalize_text(item.get("title")), item.get("volume"), item.get("pages")
        )
        unique_candidates[identity] = item
    candidates = list(unique_candidates.values())

    if not candidates:
        return None, "no_exact_crossref_candidate", []
    mapped_candidates = []
    failure_reasons = []
    for external in candidates:
        work, local_method = map_external_work(external, by_doi, by_title)
        if work is None:
            failure_reasons.append(local_method)
        else:
            mapped_candidates.append((external, work, local_method))

    # Crossref sometimes has both a historical JSTOR DOI and a newer Cambridge
    # DOI for the same article. Multiple records are safe only when every one
    # independently converges on the same local work ID.
    mapped_ids = {work["id"] for _external, work, _method in mapped_candidates}
    if len(mapped_candidates) != len(candidates) or len(mapped_ids) != 1:
        if len(candidates) > 1:
            return None, "ambiguous_crossref_candidates", candidates
        return None, failure_reasons[0], candidates

    external, work, local_method = mapped_candidates[0]
    if len(candidates) > 1:
        local_method = "convergent_crossref_records"
    return {
        "work_id": work["id"],
        "resolution_method": RESOLUTION_METHOD,
        "local_match_method": local_method,
        "crossref": external,
    }, None, candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use only already-cached Crossref years; do not access the network.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refetch all required years even when they are already cached.",
    )
    args = parser.parse_args()

    citations = load_json(INPUT_PATH)
    works = load_json(WORKS_PATH)
    if not isinstance(citations, list) or not isinstance(works, list):
        raise ValueError("Expected citation and works inputs to be JSON lists")

    targets = collect_targets(citations)
    required_years = sorted({parsed["year"] for parsed in targets.values()})
    cache = load_json(CACHE_PATH, {"issn": JSL_ISSN, "years": {}})
    if cache.get("issn") != JSL_ISSN:
        raise ValueError(f"Unexpected ISSN in {CACHE_PATH}")
    cached_years = cache.setdefault("years", {})
    mailto = os.environ.get("CROSSREF_MAILTO")

    for year in required_years:
        key = str(year)
        if key in cached_years and not args.refresh:
            print(f"[=] Using cached Crossref metadata for {year}")
            continue
        if args.offline:
            print(f"[!] No cached Crossref metadata for {year}; leaving its references unresolved")
            continue
        print(f"[*] Fetching JSL metadata from Crossref for {year}...")
        items, query_url = fetch_crossref_year(year, mailto=mailto)
        cached_years[key] = {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "query_url": query_url,
            "items": items,
        }
        write_json(CACHE_PATH, cache)
        time.sleep(0.15)

    by_doi, by_title = build_work_indexes(works)
    matches = []
    unresolved = []
    for raw_reference, parsed in targets.items():
        year_cache = cached_years.get(str(parsed["year"]))
        if not year_cache:
            unresolved.append({
                "reference": raw_reference,
                "parsed": parsed,
                "reason": "year_not_cached",
                "crossref_candidates": [],
            })
            continue
        match, reason, candidates = resolve_target(
            parsed, year_cache.get("items") or [], by_doi, by_title
        )
        if match:
            matches.append({"reference": raw_reference, "parsed": parsed, **match})
        else:
            unresolved.append({
                "reference": raw_reference,
                "parsed": parsed,
                "reason": reason,
                "crossref_candidates": candidates,
            })

    occurrence_counts = {}
    for entry in citations:
        for ref in entry.get("references", []):
            raw_reference = ref.get("reference") if isinstance(ref, dict) else None
            if raw_reference in targets:
                occurrence_counts[raw_reference] = occurrence_counts.get(raw_reference, 0) + 1

    output = {
        "method": RESOLUTION_METHOD,
        "acceptance_rule": (
            "Exact Crossref JSL year, volume, and complete page range; all provider "
            "records must converge on one merged-database work by DOI or exact "
            "normalized title/year/volume."
        ),
        "target_unique_references": len(targets),
        "target_occurrences": sum(occurrence_counts.values()),
        "matched_unique_references": len(matches),
        "matched_occurrences": sum(occurrence_counts[item["reference"]] for item in matches),
        "unresolved_unique_references": len(unresolved),
        "matches": matches,
        "unresolved": unresolved,
    }
    write_json(OUTPUT_PATH, output)
    print(f"[✓] Matched {len(matches)}/{len(targets)} unique metadata-only references")
    print(f"[✓] Matched {output['matched_occurrences']}/{output['target_occurrences']} occurrences")
    print(f"[*] Audit written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
