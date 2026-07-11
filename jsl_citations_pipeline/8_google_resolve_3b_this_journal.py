#!/usr/bin/env python3
"""Resolve short 3b "this JOURNAL" fragments through Google search.

The script extracts references such as "this JOURNAL, vol. 15, p. 141" from
active_data/3b_between_25_and_43.json, rewrites them as Journal of Symbolic
Logic searches, and queries Google Custom Search when GOOGLE_API_KEY and
GOOGLE_CSE_ID are set.

Google AI Overview is not exposed as a stable API, so this script records the
Google query, snippets, candidate metadata, and provenance instead.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


INPUT_PATH = Path("active_data/3b_between_25_and_43.json")
RESOLVED_PATH = Path("active_data/3b_google_resolved_this_journal.json")
UNRESOLVED_PATH = Path("active_data/3b_google_unresolved_this_journal.json")
AUDIT_PATH = Path("active_data/3b_google_this_journal_audit.json")
QUERY_PATH = Path("active_data/3b_google_this_journal_queries.json")


ROMAN = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
    "VI": 6,
    "VII": 7,
    "VIII": 8,
    "IX": 9,
    "X": 10,
    "XI": 11,
    "XII": 12,
    "XIII": 13,
    "XIV": 14,
    "XV": 15,
    "XVI": 16,
    "XVII": 17,
    "XVIII": 18,
    "XIX": 19,
    "XX": 20,
    "XXI": 21,
    "XXII": 22,
    "XXIII": 23,
    "XXIV": 24,
    "XXV": 25,
}


def load_refs(path):
    return json.loads(path.read_text(encoding="utf-8"))


def roman_to_int(value):
    return ROMAN.get(value.upper())


def extract_volume(raw):
    patterns = [
        r"\bvol\.?\s*(?:no\.\s*)?([0-9]+)\b",
        r"\bvo[l1]\.?\s*([0-9]+)\b",
        r"\bVOL\.?\s*([0-9]+)\b",
        r"\bJOURNAL,?\s+([IVXLCDM]+)\b",
        r"\bJOURNAL\s+([0-9]+)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        if not match:
            continue
        value = match.group(1)
        if value.isdigit():
            return int(value)
        return roman_to_int(value)
    return None


def extract_year(raw):
    match = re.search(r"\((19[0-9]{2}|20[0-9]{2})\)", raw)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(19[0-9]{2}|20[0-9]{2})\b", raw)
    return int(match.group(1)) if match else None


def extract_pages(raw):
    pages_match = re.search(
        r"\bpp?[,\.]?\s*([0-9]+)(?:\s*[-–]\s*([0-9]+))?",
        raw,
        flags=re.IGNORECASE,
    )
    if pages_match:
        start = int(pages_match.group(1))
        end = int(pages_match.group(2)) if pages_match.group(2) else start
        return start, end

    # "IV 17" means volume IV, page 17 in some older citations.
    compact = re.search(r"\bJOURNAL,?\s+([IVXLCDM]+)\s+([0-9]+)\b", raw, flags=re.IGNORECASE)
    if compact:
        page = int(compact.group(2))
        return page, page

    return None, None


def normalize_fragment(raw):
    volume = extract_volume(raw)
    year = extract_year(raw)
    start_page, end_page = extract_pages(raw)
    page_text = None
    if start_page and end_page and start_page != end_page:
        page_text = f"{start_page}-{end_page}"
    elif start_page:
        page_text = str(start_page)

    return {
        "raw_reference": raw,
        "journal": "The Journal of Symbolic Logic",
        "volume": volume,
        "year": year,
        "page_start": start_page,
        "page_end": end_page,
        "page_text": page_text,
    }


def build_queries(fragment):
    volume = fragment["volume"]
    year = fragment["year"]
    page = fragment["page_text"]
    queries = []

    if volume and page:
        if year:
            queries.append(f'"Journal of Symbolic Logic" "vol. {volume}" "{year}" "{page}"')
            queries.append(f'"Journal of Symbolic Logic" "{volume}" "{year}" "{page}"')
        queries.append(f'"Journal of Symbolic Logic" "vol. {volume}" "p. {page}"')
        queries.append(f'"Journal of Symbolic Logic" "{volume}" "{page}"')
    elif volume:
        if year:
            queries.append(f'"Journal of Symbolic Logic" "vol. {volume}" "{year}"')
        queries.append(f'"Journal of Symbolic Logic" "vol. {volume}"')

    return queries


def google_search(query, api_key, cse_id, num=5):
    params = urllib.parse.urlencode({
        "key": api_key,
        "cx": cse_id,
        "q": query,
        "num": str(num),
    })
    url = "https://www.googleapis.com/customsearch/v1?" + params
    with urllib.request.urlopen(url, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))

    results = []
    for item in data.get("items", []) or []:
        results.append({
            "title": item.get("title"),
            "link": item.get("link"),
            "snippet": item.get("snippet"),
            "display_link": item.get("displayLink"),
        })
    return results


def score_result(fragment, result):
    haystack = " ".join(
        str(result.get(key) or "")
        for key in ("title", "snippet", "link")
    ).lower()

    score = 0
    if "journal of symbolic logic" in haystack:
        score += 3
    if fragment["volume"] and re.search(rf"\b(?:vol\.?\s*)?{fragment['volume']}\b", haystack):
        score += 2
    if fragment["year"] and str(fragment["year"]) in haystack:
        score += 2
    if fragment["page_start"] and str(fragment["page_start"]) in haystack:
        score += 2
    if any(domain in haystack for domain in ("jstor", "cambridge", "projecteuclid", "doi.org", "crossref")):
        score += 1
    return score


def choose_best_result(fragment, query_results):
    scored = []
    for query, results in query_results:
        for result in results:
            scored.append({
                "query": query,
                "score": score_result(fragment, result),
                "result": result,
            })

    if not scored:
        return None

    scored.sort(key=lambda item: item["score"], reverse=True)
    best = scored[0]
    if best["score"] < 5:
        return None
    return best


def parse_args():
    parser = argparse.ArgumentParser(
        description="Google-search 3b this-JOURNAL fragments."
    )
    parser.add_argument("--input", default=str(INPUT_PATH))
    parser.add_argument("--resolved", default=str(RESOLVED_PATH))
    parser.add_argument("--unresolved", default=str(UNRESOLVED_PATH))
    parser.add_argument("--audit", default=str(AUDIT_PATH))
    parser.add_argument("--queries", default=str(QUERY_PATH))
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--no-search",
        action="store_true",
        help="Only write extracted fragments and Google query strings.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    refs = load_refs(Path(args.input))
    raw_hits = [ref for ref in refs if re.search(r"this\s+JOURNAL", ref, flags=re.IGNORECASE)]
    if args.limit:
        raw_hits = raw_hits[:args.limit]

    fragments = [normalize_fragment(raw) for raw in raw_hits]
    query_records = []
    for fragment in fragments:
        query_records.append({
            **fragment,
            "google_queries": build_queries(fragment),
            "google_search_url": (
                "https://www.google.com/search?q="
                + urllib.parse.quote_plus(build_queries(fragment)[0])
                if build_queries(fragment)
                else None
            ),
        })

    Path(args.queries).write_text(
        json.dumps(query_records, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    api_key = os.environ.get("GOOGLE_API_KEY")
    cse_id = os.environ.get("GOOGLE_CSE_ID")
    can_search = bool(api_key and cse_id) and not args.no_search

    resolved = []
    unresolved = []
    audit = []

    if not can_search:
        unresolved = [
            {
                **record,
                "reason": (
                    "no_search_requested"
                    if args.no_search
                    else "missing GOOGLE_API_KEY or GOOGLE_CSE_ID"
                ),
            }
            for record in query_records
        ]
        audit = [
            {
                **record,
                "searched": False,
                "resolved": False,
            }
            for record in query_records
        ]
    else:
        for index, record in enumerate(query_records, 1):
            print(f"Searching {index}/{len(query_records)}: {record['raw_reference']}", file=sys.stderr)
            query_results = []
            for query in record["google_queries"]:
                try:
                    results = google_search(query, api_key, cse_id)
                except Exception as exc:
                    query_results.append((query, [{"error": str(exc)}]))
                    continue
                query_results.append((query, results))
                time.sleep(args.sleep)

            best = choose_best_result(record, query_results)
            audit_record = {
                **record,
                "searched": True,
                "query_results": [
                    {"query": query, "results": results}
                    for query, results in query_results
                ],
                "resolved": bool(best),
            }

            if best:
                resolved_record = {
                    **record,
                    "source": "google_custom_search",
                    "best_query": best["query"],
                    "confidence_score": best["score"],
                    "candidate_title": best["result"].get("title"),
                    "candidate_url": best["result"].get("link"),
                    "candidate_snippet": best["result"].get("snippet"),
                }
                resolved.append(resolved_record)
                audit_record["best_result"] = resolved_record
            else:
                unresolved.append({
                    **record,
                    "reason": "no_high_confidence_google_result",
                })

            audit.append(audit_record)

    Path(args.resolved).write_text(
        json.dumps(resolved, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    Path(args.unresolved).write_text(
        json.dumps(unresolved, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    Path(args.audit).write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(
        f"Done. Extracted: {len(fragments)}, Resolved: {len(resolved)}, "
        f"Unresolved: {len(unresolved)}",
        file=sys.stderr,
    )
    print(f"Queries written to {args.queries}", file=sys.stderr)


if __name__ == "__main__":
    main()
