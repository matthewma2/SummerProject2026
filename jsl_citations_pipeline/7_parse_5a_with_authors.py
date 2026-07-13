#!/usr/bin/env python3
"""Parse jsl_citations_data/5a_with_authors.json into structured JSON entries."""

import json
import re
import sys
import unicodedata
from pathlib import Path


PARSER_PATH = Path("jsl_citations_pipeline/4_parsing_unresolved_works.py")
AUTHORS_PATH = Path("databases/authors.json")
INPUT_PATH = Path("jsl_citations_data/5a_with_authors.json")
OUTPUT_PATH = Path("jsl_citations_data/5a_parsed.json")
IGNORED_PATH = Path("jsl_citations_data/5a_ignored.txt")
ERRORS_PATH = Path("jsl_citations_data/5a_parse_errors.txt")


SPECIAL = str.maketrans({
    "Ł": "L", "ł": "l",
    "Ø": "O", "ø": "o",
    "Đ": "D", "đ": "d",
    "Æ": "Ae", "æ": "ae",
    "Œ": "Oe", "œ": "oe",
    "0": "O",
})


def norm(s):
    s = str(s).translate(SPECIAL)
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    s = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    return re.sub(r"\s+", " ", s)


def load_base_parser():
    """Load parser function definitions without executing that file's main block."""
    source = PARSER_PATH.read_text(encoding="utf-8")
    source = source.split("# 9. RUN ON ALL ENTRIES", 1)[0]
    namespace = {"__name__": "loaded_jsl_parser"}
    exec(compile(source, str(PARSER_PATH), "exec"), namespace)

    # 4a already has an author lead by construction; avoid network fallback.
    namespace["query_crossref"] = lambda *args, **kwargs: None
    namespace["query_open_library"] = lambda *args, **kwargs: None
    return namespace


def build_author_indexes():
    authors = json.loads(AUTHORS_PATH.read_text(encoding="utf-8"))

    surname_terms = set()
    full_terms = set()

    def is_first_name_only(term, full_name):
        if not term or not full_name:
            return False
        term_norm = norm(term)
        full_tokens = norm(full_name).split()
        return len(full_tokens) > 1 and term_norm == full_tokens[0]

    for author in authors:
        full = author.get("full_name") or author.get("name") or ""
        if full:
            full_norm = norm(full)
            full_terms.add(full_norm)
            parts = full_norm.split()
            if parts:
                surname_terms.add(parts[-1])

        for alt in author.get("alternative_names") or []:
            if is_first_name_only(alt, full):
                continue
            alt_norm = norm(alt)
            if not alt_norm:
                continue
            if len(alt_norm.split()) > 1:
                full_terms.add(alt_norm)
            else:
                surname_terms.add(alt_norm)

    return full_terms, surname_terms


FULL_TERMS, SURNAME_TERMS = build_author_indexes()

WORD = r"[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿĀ-ſ'’-]+"
INITIAL = r"(?:[A-ZÀ-ÖØ-Þ0]\.?\s*)"
PARTICLE = r"(?:v|von|van|de|del|der|den|di|du|le|la)"
AUTHOR_JOIN = r"(?:and|AND|und|u\.)"


def clean_author(author):
    author = author.strip(" ,.;")
    author = re.sub(r"^\[\d+\]\s*", "", author)
    author = re.sub(r"\s+", " ", author)
    author = author.replace("0.", "O.")
    return author


def split_authors(raw):
    raw = clean_author(raw)
    raw = re.sub(r"\s+in\s*$", "", raw)
    raw = re.sub(r"\s+reviewing\s*$", "", raw)
    raw = re.sub(r",\s*((?:Jr|JR|Junior)\.?)", r" \1", raw)
    parts = re.split(r"\s*,\s*(?=[A-ZÀ-ÖØ-Þ0])|\s+(?:and|AND|und|u\.)\s+", raw)
    return [clean_author(part) for part in parts if clean_author(part)]


def is_initial_period(text, period_index):
    j = period_index - 1
    while j >= 0 and text[j].isspace():
        j -= 1
    if j < 0 or not text[j].isalpha():
        return False
    k = j - 1
    while k >= 0 and text[k].isalpha():
        k -= 1
    token = text[k + 1:j + 1]
    return len(token) == 1


def is_suffix_period(text, period_index):
    j = period_index - 1
    while j >= 0 and text[j].isspace():
        j -= 1
    if j < 0 or not text[j].isalpha():
        return False
    k = j - 1
    while k >= 0 and text[k].isalpha():
        k -= 1
    token = text[k + 1:j + 1].lower()
    return token in {"jr", "junior"}


def rest_starts_with_author_continuation(rest):
    """True when a comma is probably joining another author, not starting a title."""
    rest = rest.strip()
    if re.match(r"^(?:Jr|JR|Junior)\.?,?\s+", rest):
        return True

    rest = re.sub(r"^(?:and|AND|und|u\.)\s+", "", rest)
    first_segment = re.split(r"[,;:]", rest, maxsplit=1)[0].strip()
    if not first_segment:
        return False

    if len(first_segment.split()) > 6:
        return False

    return looks_like_author_block(first_segment, norm(first_segment))


def iter_author_boundaries(text):
    """Yield possible (author_prefix, rest) splits, keeping initial periods intact."""
    candidates = []

    for m in re.finditer(r"['’]s\s+", text):
        candidates.append((m.start(), text[:m.start()], text[m.end():]))

    for m in re.finditer(r"\s+(?:in|reviewing|recently)\s+", text):
        candidates.append((m.start(), text[:m.start()], text[m.end():]))

    # No explicit delimiter: "S. C. KLEENE General recursive..." /
    # "HANS REICHENBACH Elements..." / "R. A. BULL An algebraic..."
    for m in re.finditer(r"\s+", text):
        prefix = text[:m.start()]
        rest = text[m.end():]
        if any(ch in prefix for ch in ",;:"):
            continue
        if prefix.rstrip().endswith((",", ".", ";", ":")):
            continue
        rest_first = re.match(r"([A-Za-zÀ-ÖØ-öø-ÿĀ-ſ]+)([,.;:]?)", rest)
        rest_first_word = rest_first.group(1) if rest_first else ""
        rest_first_punct = rest_first.group(2) if rest_first else ""
        prefix_norm = norm(prefix)

        if (
            (" and " in f" {prefix_norm} " or " und " in f" {prefix_norm} ")
            and rest_first_word
            and rest_first_punct in {",", "."}
        ):
            continue

        if rest_first_word and rest_first_word == rest_first_word.upper() and rest_first_punct == ",":
            continue

        if 2 <= len(prefix.split()) <= 7 and (rest[:1].isupper() or rest[:1] in {"'", '"'} or rest[:1].isdigit()):
            candidates.append((m.start(), prefix, rest))

    for idx, ch in enumerate(text):
        if ch in ",:;":
            rest = text[idx + 1:].strip()
            if rest:
                if ch == "," and rest_starts_with_author_continuation(rest):
                    continue
                candidates.append((idx, text[:idx], rest))
        elif ch == "." and not is_initial_period(text, idx) and not is_suffix_period(text, idx):
            rest = text[idx + 1:].strip()
            if rest:
                candidates.append((idx, text[:idx], rest))

    for _, prefix, rest in sorted(candidates, key=lambda candidate: candidate[0]):
        yield prefix, rest


def consume_author_prefix(text):
    """Return (authors, rest) when the string starts with a recognizable author block."""
    text = text.strip()
    text = re.sub(r"^\[\d+\]\s*", "", text)
    text = re.sub(r"^\d+\.\s+(?=[A-ZÀ-ÖØ-Þ])", "", text)

    candidates = []
    for raw, rest in iter_author_boundaries(text):
        raw = raw.strip(" ,.;:")
        rest = rest.strip()
        if not raw or not rest:
            continue
        raw_norm = norm(raw)
        if looks_like_author_block(raw, raw_norm):
            candidates.append((raw, rest))

    if candidates:
        raw, rest = candidates[0]
        rest = rest.lstrip(" ,;:")
        rest = re.sub(r"^\d+\.\s*t\s+", "", rest, flags=re.IGNORECASE)
        rest = re.sub(r"^\d+\.\s+", "", rest)
        return split_authors(raw), rest

    return [], text


def looks_like_author_block(raw, raw_norm):
    tokens = raw_norm.split()
    if not tokens:
        return False

    if tokens[-1] in {"and", "und", "u"}:
        return False

    if len(tokens[-1]) == 1 and raw_norm not in FULL_TERMS:
        return False

    if raw.count("(") != raw.count(")"):
        return False

    raw_norm = re.sub(r"\b(ed|jr|junior)\b", "", raw_norm).strip()

    if raw_norm in FULL_TERMS:
        return True

    compact = raw_norm.replace(" ", "")
    if any(compact == term.replace(" ", "") for term in FULL_TERMS):
        return True

    non_initials = [
        tok for tok in raw_norm.split()
        if len(tok) > 1 and tok not in {"and", "und", "u", "jr", "ed"}
    ]

    initials = re.findall(r"(?:^|\s)[A-ZÀ-ÖØ-Þ0]\.", raw)
    if len(non_initials) == 1 and initials and len(tokens) <= 4:
        return True

    if non_initials and non_initials[-1] in SURNAME_TERMS:
        return True

    # Multi-author surname-only blocks: "Whitehead and Russell", "Hilbert and Ackermann".
    name_tokens = [tok for tok in raw_norm.split() if tok not in {"and", "und", "u"} and len(tok) > 1]
    if len(name_tokens) >= 2 and all(tok in SURNAME_TERMS for tok in name_tokens[-2:]):
        return True

    if len(name_tokens) == 1 and name_tokens[0] in SURNAME_TERMS:
        return True

    # Corpus-specific all-caps or mixed author headers can include authors absent
    # from authors.json, e.g. "ERNEST A. MOODY".
    letters = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿĀ-ſ]", "", raw)
    has_upper_word = any(len(tok) > 1 and tok == tok.upper() for tok in re.findall(r"[A-Za-zÀ-ÖØ-ÞĀ-ſ]+", raw))
    return bool(letters) and has_upper_word and len(tokens) <= 6


def extract_authors_for_4a(text):
    authors, rest = consume_author_prefix(text)
    return authors, rest


def parse_one_with_base(base, raw):
    return base["parse_one"](raw)


def main():
    base = load_base_parser()
    base["extract_authors"] = extract_authors_for_4a

    refs = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    parsed = []
    ignored = []
    errors = []

    print(f"Processing {len(refs)} reference strings...", file=sys.stderr)

    for i, raw in enumerate(refs):
        if i % 100 == 0:
            print(f"  {i}/{len(refs)}", file=sys.stderr)
        try:
            result, reason = parse_one_with_base(base, raw)
            if result is None:
                ignored.append((raw, reason))
            else:
                result["raw_reference"] = raw
                parsed.append(result)
        except Exception as exc:
            errors.append((raw, str(exc)))
            ignored.append((raw, "ParseError"))

    OUTPUT_PATH.write_text(
        json.dumps(parsed, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    IGNORED_PATH.write_text(
        "".join(f'- "{raw}" [{reason}]\n' for raw, reason in ignored),
        encoding="utf-8",
    )

    if errors:
        ERRORS_PATH.write_text(
            "".join(f"ERROR: {err}\n  RAW: {raw}\n\n" for raw, err in errors),
            encoding="utf-8",
        )

    print(
        f"Done. Parsed: {len(parsed)}, Ignored: {len(ignored)}, Errors: {len(errors)}",
        file=sys.stderr,
    )
    print(f"Output written to {OUTPUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
