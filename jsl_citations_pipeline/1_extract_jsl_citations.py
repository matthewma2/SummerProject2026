# ============================================================
# active_scripts/extract_jsl_citations.py
# Resolve JSL citation references against works.json and write
# the resolved and unresolved reference outputs.
# ============================================================
import json
import re
import unicodedata
from difflib import SequenceMatcher

# --- CONFIGURATION ---
WORKS_FILE = "active_data/works.json"
JSL_CITATIONS_FILE = "active_data/jsl_citations.json"
OUTPUT_FILE = "active_data/jsl_citations_resolved.json"
RESOLVED_REFERENCES_FILE = "active_data/1a_resolved.json"
UNRESOLVED_REFERENCES_FILE = "active_data/1b_unresolved.json"

# Multilingual stop words list to remove noise from titles/citations
STOP_WORDS = {
    # English
    'the', 'and', 'of', 'in', 'for', 'to', 'a', 'an', 'is', 'that', 'on', 'with',
    'by', 'as', 'at', 'from', 'it', 'its', 'are', 'this', 'not', 'or', 'be',
    # German
    'der', 'die', 'das', 'von', 'zu', 'und', 'in', 'den', 'dem', 'des', 'ein', 'eine',
    # French
    'le', 'la', 'les', 'et', 'un', 'une', 'en', 'dans', 'pour', 'du', 'des', 'par'
}

# Tokens that appear in author-like positions but are not surnames
AUTHOR_IGNORED = {'and', 'von', 'van', 'der', 'the', 'this', 'vol', 'journal', 'review'}
FUZZY_TOKEN_MATCH_THRESHOLD = 0.78


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

def strip_diacritics(s):
    """
    Decompose unicode and drop combining marks, so that 'Gödel' → 'Godel',
    'Über' → 'Uber', 'für' → 'fur', etc.  This is applied before any regex
    tokenisation so that ASCII-only character classes still match names that
    contain diacritics in the source or in OCR output.
    """
    s = str(s).translate(str.maketrans({
        'Ł': 'L',
        'ł': 'l',
        'Ø': 'O',
        'ø': 'o',
        'Đ': 'D',
        'đ': 'd',
        'Þ': 'Th',
        'þ': 'th',
        'Æ': 'Ae',
        'æ': 'ae',
        'Œ': 'Oe',
        'œ': 'oe',
    }))
    return ''.join(
        c for c in unicodedata.normalize('NFD', str(s))
        if unicodedata.category(c) != 'Mn'
    )


def rejoin_hyphenated_linebreaks(s):
    """
    OCR'd text frequently carries line-wrap hyphenation like 'Mathe- matik' or
    'North- Holland', where a word was split across the original printed line.
    Left alone, tokenization would split these into unrelated fragments
    ('mathe', 'matik') that fail to match the unhyphenated word elsewhere.
    Join 'word- word' back into 'wordword' before tokenizing.
    """
    return re.sub(r'(\w)-\s+(\w)', r'\1\2', str(s))


def tokenize_string(s):
    """
    Splits a string into a set of lower-case alphanumeric words, filtering out
    stop words.  Diacritics are stripped first so that unicode titles in
    works.json and ASCII-normalised OCR output produce the same tokens.
    """
    if not s:
        return set()
    words = re.findall(r'\b\w{3,}\b', strip_diacritics(rejoin_hyphenated_linebreaks(s)).lower())
    return {w for w in words if w not in STOP_WORDS}


def fuzzy_token_overlap(ref_tokens, candidate_tokens):
    """Count exact plus close OCR/typo token matches between two token sets."""
    exact_matches = ref_tokens.intersection(candidate_tokens)
    matched_candidate_tokens = set(exact_matches)
    overlap = len(exact_matches)

    for ref_token in ref_tokens - exact_matches:
        if len(ref_token) < 5:
            continue
        for candidate_token in candidate_tokens - matched_candidate_tokens:
            if len(candidate_token) < 5:
                continue
            if SequenceMatcher(None, ref_token, candidate_token).ratio() >= FUZZY_TOKEN_MATCH_THRESHOLD:
                matched_candidate_tokens.add(candidate_token)
                overlap += 1
                break

    return overlap


def normalize_text(s):
    """Normalize journal/title-like text for comparison."""
    if not s:
        return ""
    return re.sub(r'[^a-z0-9\s]+', '', strip_diacritics(str(s)).lower()).strip()


def extract_vol_number(s):
    """Extract an integer volume number from a string (e.g. 'Vol. 1' or 'vol. 38')."""
    if not s:
        return None
    m = re.search(r'\bvol\.?\s*(\d+)', str(s), re.IGNORECASE)
    return int(m.group(1)) if m else None


def extract_journal_volume(reference_string):
    """Extract a normalized journal title and volume from a reference string."""
    if not reference_string:
        return None, None

    ref = reference_string.replace('\n', ' ').strip()
    match = re.search(r'(?P<journal>[^,]+?),\s*vol(?:ume)?\.?\s*(?P<volume>\d+)', ref, re.IGNORECASE)
    if match:
        return normalize_text(match.group('journal')), match.group('volume').strip()

    match = re.search(r'(?P<journal>[^,]+?),\s*no\.?\s*(?P<volume>\d+)', ref, re.IGNORECASE)
    if match:
        return normalize_text(match.group('journal')), match.group('volume').strip()

    return None, None


def is_loc_cit(reference_string):
    """Return True if this reference is a 'loc. cit.' or 'ibid.' back-reference."""
    return bool(re.search(r'\bloc\.?\s*cit\.?\b|\bibid\.?\b', reference_string, re.IGNORECASE))


def extract_year_and_authors(reference_string):
    """
    Extracts a 4-digit year and all potential author name tokens found prior to
    the title metadata.  Diacritics are stripped before the ASCII character-class
    regex runs so that surnames like 'Gödel' → 'Godel' are captured correctly.
    """
    year_match = re.search(r'\b(1[89]\d{2})\b', reference_string)
    year = int(year_match.group(1)) if year_match else None

    if "," in reference_string:
        author_segment = reference_string.split(",", 1)[0]
    elif year_match:
        author_segment = reference_string.split(year_match.group(1), 1)[0]
    else:
        author_segment = reference_string

    author_segment = re.sub(r'\[\d+\]', '', author_segment)
    normalized_author_segment = strip_diacritics(author_segment).lower()
    # Strip diacritics before ASCII-only regex so 'Gödel' → 'Godel' etc.
    author_tokens = re.findall(r'\b[a-zA-Z]{3,}\b', normalized_author_segment)
    author_hints = [w for w in author_tokens if w not in AUTHOR_IGNORED]

    # For a single named person ("Max Black", "Alonzo Church"), the last token is
    # the surname. Coauthor strings joined by "and" keep each surname-like token.
    if len(author_hints) > 1 and " and " not in f" {normalized_author_segment} ":
        author_hints = [author_hints[-1]]

    return year, author_hints


# ---------------------------------------------------------------------------
# Index construction
# ---------------------------------------------------------------------------

def build_year_index(works_data):
    """
    Builds an optimized resolution structure: index[year][author_token] = [records…]
    Incorporates primary and alternative titles.
    """
    index = {}
    for work in works_data:
        year = work.get("year")
        if year is None:
            continue
        try:
            year_key = int(year)
        except (ValueError, TypeError):
            continue

        if year_key not in index:
            index[year_key] = {"_ALL_RECORDS_": []}

        record = _make_record(work)
        index[year_key]["_ALL_RECORDS_"].append(record)

        author_tokens = _extract_author_tokens(work)
        if author_tokens:
            for token in author_tokens:
                index[year_key].setdefault(token, []).append(record)
        else:
            index[year_key].setdefault("_UNKNOWN_AUTHOR_", []).append(record)

    return index


def build_author_index(works_data):
    """
    Builds a year-agnostic index: author_token -> [records].
    Used as a fallback when a reference contains no year.
    """
    index = {}
    for work in works_data:
        record = _make_record(work)
        for token in _extract_author_tokens(work):
            index.setdefault(token, []).append(record)
    return index


def _make_record(work):
    """Build the scoring record for a work, including all title variants and metadata tokens."""
    title = work.get("title", "")
    title_tokens = tokenize_string(title)
    for alt_title in work.get("alternative_titles") or []:
        title_tokens.update(tokenize_string(alt_title))

    # Secondary scoring tokens from notes and location (used only for tiebreaking)
    meta_tokens = tokenize_string(work.get("notes", ""))
    meta_tokens.update(tokenize_string(work.get("location", "")))

    return {
        "id": work.get("id"),
        "title_tokens": title_tokens,
        "meta_tokens": meta_tokens,
        "year": work.get("year"),
        "journal_norm": normalize_text(work.get("journal", "")),
        "volume": str(work.get("volume")) if work.get("volume") is not None else None,
        # Volume hint derived from title or notes (e.g. Frege's Vol. 1, Principia notes)
        "vol_hint": extract_vol_number(title) or extract_vol_number(work.get("notes", "")),
    }


def _extract_author_tokens(work):
    """Return the set of normalised author-surname tokens for a work."""
    ignored = {'the', 'cynic', 'von', 'van', 'der', 'and'}
    tokens = set()
    for author in work.get("authors", []):
        for w in re.findall(r'\b[a-zA-Z]{3,}\b', strip_diacritics(author).lower()):
            if w not in ignored:
                tokens.add(w)
    return tokens


# ---------------------------------------------------------------------------
# Candidate retrieval
# ---------------------------------------------------------------------------

def _year_bucket_candidates(year, author_hints, works_index):
    """
    Retrieve candidates from the year bucket.

    Priority 1: Records indexed under at least one matching author token.
    Priority 2 (if no author matches): Journal/volume match across all year records.
    Priority 3 (if author_hints is empty): All records in the year bucket, to be
               disambiguated purely by title-token overlap.
    """
    if year not in works_index:
        return {}

    year_bucket = works_index[year]
    candidates = {}

    for hint in author_hints:
        if hint in year_bucket:
            for candidate in year_bucket[hint]:
                candidates[candidate["id"]] = candidate

    return candidates


def _all_year_candidates(year, works_index):
    """Return all records for a given year (used when no author hints are available)."""
    if year not in works_index:
        return {}
    return {c["id"]: c for c in works_index[year].get("_ALL_RECORDS_", [])}


def _yearless_candidates(author_hints, author_index):
    """
    Find candidates across all years that match ALL supplied author hints (intersection).

    When there is only a single author hint, "intersection" and "union" are the same
    set, so there's nothing to fall back to. When there are multiple author hints
    (e.g. a co-authored reference like "DAIGNEAULT and MONK"), an empty intersection
    means no single work in the database is credited to *all* of the cited authors.
    In that case we deliberately do NOT fall back to the union of each author's solo
    works -- doing so previously caused a co-authored reference to be silently merged
    into an unrelated single-author record (e.g. "Daigneault and Monk" resolving to a
    Daigneault-only work). Leaving it unresolved is the correct, honest outcome.
    """
    hint_sets = [author_index.get(h, []) for h in author_hints if h in author_index]
    if not hint_sets:
        return {}

    if len(hint_sets) == 1:
        common_ids = {c["id"] for c in hint_sets[0]}
    else:
        id_sets = [set(c["id"] for c in recs) for recs in hint_sets]
        common_ids = id_sets[0].intersection(*id_sets[1:])
        if not common_ids:
            # No work is credited to every cited co-author -- do not guess.
            return {}

    id_to_record = {}
    for recs in hint_sets:
        for c in recs:
            if c["id"] in common_ids:
                id_to_record[c["id"]] = c
    return id_to_record


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

BIB_FILLER_WORDS = {
    'vol', 'volume', 'no', 'pp', 'page', 'pages', 'doctoral', 'dissertation',
    'thesis', 'forthcoming', 'appear', 'reprint', 'reprinted', 'press',
    'university', 'edition', 'ed', 'edn', 'aufl', 'auflage', 'revised',
    'band', 'supplement', 'trans', 'translated', 'translation',
}


def extract_title_segment(reference_string):
    """
    Best-effort extraction of just the title portion of a reference string.
    In this bibliography's citation style, a reference is typically
    "AUTHOR, Title. Venue, year, pp..." or "AUTHOR, Title, vol. N (year)...",
    so the title reliably sits between the author's comma and the first clear
    venue boundary: a sentence-ending period, or a comma introducing "vol.",
    "to appear", "doctoral dissertation", etc. This is a heuristic (it can
    over- or under-cut on unusual formats) -- it's only used as a secondary
    sanity check, never as the primary matching signal.
    """
    ref = reference_string.replace('\n', ' ').strip()
    rest = ref.split(',', 1)[1].strip() if ',' in ref else ref

    period_match = re.search(r'\.\s+', rest)
    venue_match = re.search(
        r',\s*(?:to appear|forthcoming|doctoral dissertation|thesis|vol\.?|'
        r'volume|no\.?)\b',
        rest, re.IGNORECASE
    )

    cut_points = [m.start() for m in (period_match, venue_match) if m]
    if cut_points:
        return rest[:min(cut_points)]
    return rest


def score_candidate(ref_tokens, ref_vol, ref_year_hint, candidate):
    """
    Returns a comparable tuple: (title_overlap, vol_match, year_bonus, meta_bonus).
    Higher is better on every component.
    """
    title_overlap = fuzzy_token_overlap(ref_tokens, candidate["title_tokens"])

    # Volume-number tiebreaker (especially useful for multi-volume works like Principia)
    vol_match = 0
    if ref_vol is not None and candidate.get("vol_hint") is not None:
        vol_match = 1 if ref_vol == candidate["vol_hint"] else -1

    # If a year appeared somewhere in the reference, prefer works from that year
    year_bonus = 0
    if ref_year_hint is not None and candidate.get("year") is not None:
        try:
            year_bonus = 1 if int(candidate["year"]) == ref_year_hint else 0
        except (ValueError, TypeError):
            pass

    # Light boost for meta-token overlap (notes, location)
    meta_bonus = len(ref_tokens.intersection(candidate["meta_tokens"]))

    return (title_overlap, vol_match, year_bonus, meta_bonus)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def resolve_reference(raw_ref, works_index, author_index):
    """
    Resolve a single raw reference string to a work ID.
    Returns (id_or_None, was_resolved).
    """
    year, author_hints = extract_year_and_authors(raw_ref)
    ref_tokens_raw = tokenize_string(raw_ref)
    ref_tokens = ref_tokens_raw - set(author_hints)
    ref_vol = extract_vol_number(raw_ref)

    candidates = {}
    used_yearless = False

    # 1. Year-bucket: author-based candidates
    if year and year in works_index:
        candidates = _year_bucket_candidates(year, author_hints, works_index)

        # 1b. Journal/volume fallback within the year bucket
        if not candidates:
            journal, volume = extract_journal_volume(raw_ref)
            if journal and volume:
                for candidate in works_index[year].get("_ALL_RECORDS_", []):
                    if candidate.get("journal_norm") == journal and candidate.get("volume") == volume:
                        candidates[candidate["id"]] = candidate

        # 1c. No-author fallback: score ALL records in the year bucket by title overlap.
        #     Only used when author hints are empty (e.g. "K. Gödel" with diacritic issue
        #     fully stripped, or title-only citation) — kept strictly separate so we don't
        #     bloat candidate sets for normal cases.
        if not candidates and not author_hints:
            candidates = _all_year_candidates(year, works_index)

    # 2. Year-agnostic global author index (reference has no year bucket to search,
    #    either because none was parsed, or because the parsed year isn't in the DB)
    if not candidates and author_hints:
        candidates = _yearless_candidates(author_hints, author_index)
        used_yearless = True

    if not candidates:
        return None, False

    # Flag the riskiest kind of match before scoring: a yearless resolution where
    # the cited author only has ONE work in the database at all, AND the reference
    # doesn't look like a normal "journal, vol. N" citation (so there's no
    # volume/journal corroboration either). Such a match is accepted purely on
    # "this person has exactly one entry" rather than real evidence, which lets a
    # reference for a genuinely different work (e.g. a PhD dissertation) latch
    # onto that person's one indexed journal article just because it's the only
    # thing available. These get an extra title-segment check further down.
    is_single_candidate_monopoly = used_yearless and len(candidates) == 1
    if is_single_candidate_monopoly:
        _journal, _volume = extract_journal_volume(raw_ref)
        is_single_candidate_monopoly = _journal is None

    # --- Score all candidates ---
    # When using yearless matching, pass the year extracted from the ref as a hint so
    # same-year candidates are preferred.
    year_hint_for_scoring = year if used_yearless else None

    best_id = None
    best_score = None
    is_tie = False

    for cand_id, candidate in candidates.items():
        score = score_candidate(ref_tokens, ref_vol, year_hint_for_scoring, candidate)
        if score[0] == 0:  # Zero title overlap — reject immediately
            continue
        if best_score is None or score > best_score:
            best_score = score
            best_id = cand_id
            is_tie = False
        elif score == best_score:
            is_tie = True

    if best_id is None or is_tie:
        return None, False

    title_overlap = best_score[0]

    # Adaptive overlap threshold:
    # - Short-titled works (1–2 content tokens) only need overlap ≥ 1 when year-based.
    # - Year-agnostic search is inherently less precise → require ≥ 2 regardless.
    min_overlap = 1 if len(candidates[best_id]["title_tokens"]) <= 2 else 2
    if used_yearless:
        min_overlap = max(min_overlap, 2)

    # For the no-author / all-year-bucket fallback, require stronger title evidence
    # to avoid spurious matches across a busy year bucket.
    if not author_hints and year is not None:
        min_overlap = max(min_overlap, 3)

    if title_overlap < min_overlap:
        return None, False

    if used_yearless:
        candidate_title_len = len(candidates[best_id]["title_tokens"])
        if candidate_title_len and (title_overlap / candidate_title_len) < 0.5:
            return None, False

    if is_single_candidate_monopoly:
        # Compare just the extracted title segment against the candidate's title,
        # rather than the candidate-side overlap used above -- this is the one
        # situation where "most of the candidate's title words are covered" isn't
        # enough evidence, since the only reason this candidate is here is that
        # it's the author's sole DB entry, not because a year, volume, or journal
        # corroborated it. Filler words and bare numbers are stripped from both
        # sides first since they're not really "title" content and otherwise
        # distort the comparison in both directions.
        _filler = BIB_FILLER_WORDS
        title_segment_tokens = {
            t for t in tokenize_string(extract_title_segment(raw_ref))
            if t not in _filler and not t.isdigit()
        }
        candidate_title_tokens = {
            t for t in candidates[best_id]["title_tokens"] if t not in _filler
        }
        if title_segment_tokens and candidate_title_tokens:
            overlap = fuzzy_token_overlap(title_segment_tokens, candidate_title_tokens)
            denom = len(title_segment_tokens) + len(candidate_title_tokens) - overlap
            jaccard = overlap / denom if denom else 0
            if jaccard < 0.55:
                return None, False

    return best_id, True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"[*] Loading works data from {WORKS_FILE}...")
    with open(WORKS_FILE, 'r', encoding='utf-8') as f:
        works_data = json.load(f)

    works_index = build_year_index(works_data)
    author_index = build_author_index(works_data)
    print(f"[✓] Successfully indexed {len(works_data)} works.")

    print(f"[*] Loading raw citations from {JSL_CITATIONS_FILE}...")
    with open(JSL_CITATIONS_FILE, 'r', encoding='utf-8') as f:
        jsl_data = json.load(f)

    resolved_count = 0
    skipped_count = 0
    unresolved_count = 0
    loc_cit_count = 0
    resolved_reference_strings = []
    unresolved_reference_strings = []

    print("[*] Resolving reference string matches...")
    for entry in jsl_data:
        source = entry.get("source", "")
        refs = entry.get("references", [])

        # Per-source list of (author_hints, resolved_id) for loc. cit. back-resolution
        source_resolved_history = []

        for ref_obj in refs:
            raw_ref = ref_obj.get("reference", "")

            # Skip trivially short internal shorthands like "[3]"
            if re.match(r'^\[\d+\]\s*(.*)$', raw_ref.strip()) and len(raw_ref.strip()) < 15:
                ref_obj["id"] = None
                skipped_count += 1
                continue

            # --- Handle loc. cit. / ibid. back-references ---
            if is_loc_cit(raw_ref):
                _, loc_author_hints = extract_year_and_authors(raw_ref)
                matched_id = None

                # Walk backwards through this source's resolved history.
                for prev_hints, prev_id in reversed(source_resolved_history):
                    if prev_id is None:
                        continue
                    if loc_author_hints:
                        if any(h in prev_hints for h in loc_author_hints):
                            matched_id = prev_id
                            break
                    else:
                        matched_id = prev_id
                        break

                ref_obj["id"] = matched_id
                if matched_id:
                    resolved_reference_strings.append({
                        "reference": raw_ref,
                        "id": matched_id,
                    })
                    loc_cit_count += 1
                    resolved_count += 1
                else:
                    unresolved_reference_strings.append(raw_ref)
                    unresolved_count += 1
                # Don't push loc. cit. entries onto history (they're not primary citations)
                continue

            # --- Normal resolution ---
            resolved_id, ok = resolve_reference(raw_ref, works_index, author_index)
            ref_obj["id"] = resolved_id

            _, author_hints = extract_year_and_authors(raw_ref)
            source_resolved_history.append((author_hints, resolved_id))

            if ok:
                resolved_reference_strings.append({
                    "reference": raw_ref,
                    "id": resolved_id,
                })
                resolved_count += 1
            else:
                unresolved_reference_strings.append(raw_ref)
                unresolved_count += 1

    print(f"[*] Saving resolved structures to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(jsl_data, f, indent=4, ensure_ascii=False)

    print(f"[*] Saving resolved reference strings to {RESOLVED_REFERENCES_FILE}...")
    with open(RESOLVED_REFERENCES_FILE, 'w', encoding='utf-8') as f:
        json.dump(resolved_reference_strings, f, indent=4, ensure_ascii=False)

    print(f"[*] Saving unresolved reference strings to {UNRESOLVED_REFERENCES_FILE}...")
    with open(UNRESOLVED_REFERENCES_FILE, 'w', encoding='utf-8') as f:
        json.dump(unresolved_reference_strings, f, indent=4, ensure_ascii=False)

    print("\n[✓] Execution Completed Successfully!")
    print(f"    - Matches Resolved (Unique ID Assigned): {resolved_count}")
    print(f"      of which loc. cit. / ibid. back-refs:  {loc_cit_count}")
    print(f"    - Internal Structural Shortcuts Skipped: {skipped_count}")
    print(f"    - Remaining Unresolved Items left as null: {unresolved_count}")
    print(f"    - Resolved reference strings saved: {len(resolved_reference_strings)}")
    print(f"    - Unresolved reference strings saved: {len(unresolved_reference_strings)}")


if __name__ == "__main__":
    main()