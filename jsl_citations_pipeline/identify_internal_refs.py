"""
filter_internal_refs.py

Filters "internal" / back-reference style entries out of a list of raw
JSL bibliographic reference strings, leaving the strings that look like
genuine, resolvable bibliographic citations (author + title + venue/year).

"Internal references" here means: short pointers that only make sense in
the context of the surrounding article text -- e.g. bare footnote numbers,
bracketed numeric/roman-numeral citation markers, bare "Author (Year)"
pointers, "this JOURNAL, vol. X, p. Y" fragments with no title, "Title, p.
X" continuation fragments, "See Author (Year)" cross-references, and
ibid./loc. cit./op. cit. markers.

Each filtered string is tagged with the rule that caught it, so the output
can be spot-checked (performance review) rather than trusted blindly --
these are heuristics on messy OCR text, not a guarantee.

Usage:
    python3 filter_internal_refs.py input.json
Outputs (next to the input file):
    <stem>_filtered_internal.json   - removed entries, with the matching rule
    <stem>_kept_full_refs.json      - entries kept as likely full references
    <stem>_review_summary.txt       - counts per rule + samples for review
"""

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Rule definitions (checked in order; first match wins)
# ---------------------------------------------------------------------------

ROMAN_RE = r"[IVXLCDM]+"

NAME_WORD = r"[A-ZÀ-Ý][\wÀ-ÿ''\-\.]*"
NAME = rf"{NAME_WORD}(?:\s+{NAME_WORD})*"
AUTHORS = rf"{NAME}(?:\s*(?:and|&)\s*{NAME}|\s+et al\.?)?"
YEAR = r"\d{4}[a-z]?"
PAGEREF = r"p{1,2}\.\s*[ivxlcdmIVXLCDM\d\-,\s]+f{0,2}\.?"

RULES = []


def rule(name, pattern, flags=0):
    """Register a regex rule; pattern is matched against the *stripped* string."""
    RULES.append((name, re.compile(pattern, flags)))


# 1. Bare footnote/note numbers: "6", "7.", "12"
rule("BARE_NUMBER", r"^\d{1,3}\.?$")

# 2. Bracketed numeric citation markers: "[91", "[11", "10] p. 359",
#    "[ 18], pp. 204-205", "8] p. 19", "[28A]", "[14'"
rule(
    "BRACKET_NUM_REF",
    rf"^\[?\s*\d{{1,3}}[A-Za-z]?\s*\]?['\"]?\s*,?\s*(?:{PAGEREF})?\.?$",
)

# 3. Bracketed roman-numeral labels: "[I] pp. 91 ff", "[I], p. 240", "[I] §§14 ff"
rule(
    "BRACKET_LABEL_REF",
    rf"^\[\s*{ROMAN_RE}\s*\]\s*,?\s*(?:{PAGEREF}|§§?\s*[\d.]+\s*ff\.?)?\.?$",
)

# 4. Volume/page fragments with no author or title:
#    "vol. 31 (1928), pp. 261-291", "Bd. 73 (1913), S. 245-272",
#    "errata, vol. 23, p. vi.", "Vol. XIV (1963), pp. 12-28"
rule(
    "VOL_FRAGMENT",
    rf"^(?:errata,\s*)?(?:vol\.|Vol\.|VOl\.|Vo1\.|Bd\.)\s*(?:\d+|{ROMAN_RE})\b.*$",
)

# 5. "this JOURNAL" fragments handled separately below (journal_fragment_check)
# -- a plain regex over-matches real (if author-less) titles like
# "Logic based on inclusion and abstraction, this JOURNAL, ...".

# Words that signal real title content (as opposed to a bare personal name)
# immediately before "this JOURNAL" / "in this JOURNAL".
_TITLE_INDICATOR_WORDS = {
    "of", "on", "in", "for", "with", "without", "the", "a", "an", "to",
    "from", "by", "his", "her", "their", "review", "reviews", "recursive",
    "computability", "sequence", "sequences", "model", "models",
    "elimination", "implication", "axiomatizability", "quantification",
    "quantifiers", "quantifier", "number", "numbers", "derivability",
    "simplicity", "type", "types", "logic", "logical", "basic", "system",
    "systems", "theory", "theories", "paradox", "calculus",
    "completeness", "consistency", "decision", "problem", "problems",
    "definability", "function", "functions", "predicate", "predicates",
    "postulate", "postulates", "extension", "notation", "ordinal",
    "ordinals", "virtual", "class", "classes", "real", "weakened",
    "simple", "formal", "axiomatic", "set", "sets", "modality",
    "modalities", "modal", "idem", "universals", "abstraction",
    "inclusion", "based", "appeared", "part", "parts", "paper",
}
_NAME_TOKEN_RE = re.compile(r"^[A-ZÀ-Ý][\wÀ-ÿ''\-]*\.?$")
_NAME_CONNECTORS = {"and", "&", "et", "al.", "al", "von", "van", "de", "der", "jr.", "jr"}


def _is_name_like(precursor: str) -> bool:
    """True if `precursor` looks like a bare author byline (no real title)."""
    precursor = precursor.strip(" ,.")
    if not precursor:
        return True  # nothing before "this JOURNAL" at all
    words = precursor.split()
    if len(words) > 6:
        return False
    lowered = {w.lower().strip(".,") for w in words}
    if lowered & _TITLE_INDICATOR_WORDS:
        return False
    for w in words:
        wl = w.lower().strip(".,")
        if wl in _NAME_CONNECTORS:
            continue
        if not _NAME_TOKEN_RE.match(w):
            return False
    return True


_THIS_JOURNAL_SPLIT_RE = re.compile(
    r"^(?P<pre>.*?)(?:,\s*(?:this JOURNAL)|(?:\bin\s+this JOURNAL))", re.IGNORECASE
)


def journal_fragment_check(s: str):
    if re.match(r"^(?:this JOURNAL|of this JOURNAL)\b", s, re.IGNORECASE):
        return "JOURNAL_FRAGMENT"
    m = _THIS_JOURNAL_SPLIT_RE.match(s)
    if m and _is_name_like(m.group("pre")):
        return "JOURNAL_FRAGMENT"
    return None

# 6. "Author (Year)" / "Author Year" / "Author (Year, p. X)" with nothing else
rule(
    "AUTHOR_YEAR_ONLY",
    rf"^{AUTHORS}'?s?\s*(?:\(\s*{YEAR}(?:\s*,\s*{PAGEREF})?\s*\)(?:\s*,\s*{PAGEREF})?|{YEAR}(?:\s*,\s*{PAGEREF})?)\.?$",
)

# 7. "Author and Author (p. X)" -- page pointer with no year
rule(
    "AUTHOR_PAGE_ONLY",
    rf"^{AUTHORS}\s*\(\s*{PAGEREF}\s*\)\.?$",
)

# 8. Short "Title, p. X" / "p. X of Title" continuation fragments (no year,
#    no author capitalisation pattern, no journal/publisher keyword)
rule(
    "SHORT_TITLE_PAGE_ONLY",
    rf"^(?:[A-Z][\w' ]{{2,30}},\s*{PAGEREF}\.?|{PAGEREF}\s+of\s+[A-Z][\w' ]{{2,30}}\.?)$",
)

# 9. "See Author (Year)" / "Compare Author, ..." cross references
rule(
    "SEE_BACKREF",
    r"^.{0,40}?\bSee\s+[A-Z][\w.''\- ]+\(?\d{4}\)?\.?$"
    r"|^Compare\s+[A-Z][\w.''\- ]+,.{0,40}$",
)

# 11. "Author (N)" / "Author in (N)" -- author plus a bare numbered
#     bibliography pointer, e.g. "Zermelo (8)", "Bernays (9), p. 9"
rule(
    "AUTHOR_BRACKET_NUM",
    rf"^{AUTHORS}\s+(?:in\s+)?\(\s*\d{{1,3}}[A-Za-z]?\s*\)(?:,\s*{PAGEREF})?\.?$",
)

# 12. Bare number/range + page pointer, e.g. "1 (p. 218)", "10\u201313 (p. 222)"
rule(
    "NUM_RANGE_PAGE",
    r"^\d{1,3}(?:[\u2013\-]\d{1,3})?\s*\(p{1,2}\.\s*\d+(?:[\-,]\s*\d+)?\)\.?$",
)

# 13. "FootnoteN" / "Footnote N" used as a whole entry
rule("FOOTNOTE_MARKER", r"^[Ff]ootnote\s*\d+\.?$")

# 14. ibid. used as a standalone whole entry, e.g. "Ibid., vol. 14 (1949), pp. 81-84."
rule(
    "IBID",
    r"^ibid\.?(?:,\s*.{0,60})?$",
    re.IGNORECASE,
)

# 15. Latin/French/German cross-reference markers: l.c., loc. cit., op. cit.,
#     cf., supra, "Voir ..." (Fr. "See"), "Siehe ..."/"Vgl."/"ferner" (Ger.)
rule(
    "FOREIGN_OR_LATIN_BACKREF",
    r"^(?:Voir|Siehe|Vgl\.|ferner)\b.{0,40}$"
    r"|^.{0,30}\(?(?:l\.c\.|loc\.\s*cit\.?|op\.\s*cit\.?|v\.\s*supra)\b.{0,40}$"
    r"|^.{0,30}\(\s*cf\.\s*[A-Z][\w. ]{0,30}\)\.?$",
    re.IGNORECASE,
)


RULES.insert(
    [n for n, _ in RULES].index("VOL_FRAGMENT") + 1,
    ("JOURNAL_FRAGMENT", re.compile(r"(?!x)x")),  # never matches; classify() handles it specially
)


def classify(entry: str):
    s = entry.strip()
    for name, pat in RULES:
        if pat.match(s):
            return name
        if name == "VOL_FRAGMENT":
            jf = journal_fragment_check(s)
            if jf:
                return jf
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 filter_internal_refs.py <input.json>")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    data = json.loads(in_path.read_text(encoding="utf-8"))

    filtered = []  # [{"text":..., "rule":...}, ...]
    kept = []

    for entry in data:
        rule_name = classify(entry)
        if rule_name:
            filtered.append({"text": entry, "rule": rule_name})
        else:
            kept.append(entry)

    stem = in_path.stem
    out_dir = in_path.parent

    filtered_path = out_dir / f"{stem}_filtered_internal.json"
    kept_path = out_dir / f"{stem}_kept_full_refs.json"
    summary_path = out_dir / f"{stem}_review_summary.txt"

    filtered_path.write_text(
        json.dumps(filtered, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    kept_path.write_text(
        json.dumps(kept, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # --- review summary ---
    from collections import Counter

    counts = Counter(f["rule"] for f in filtered)
    lines = []
    lines.append(f"Input: {in_path.name}")
    lines.append(f"Total entries: {len(data)}")
    lines.append(f"Filtered out (internal refs): {len(filtered)}")
    lines.append(f"Kept (likely full refs): {len(kept)}")
    lines.append("")
    lines.append("Filtered counts by rule:")
    for name, _ in RULES:
        c = counts.get(name, 0)
        lines.append(f"  {name}: {c}")
    lines.append("")
    lines.append("Sample filtered entries per rule (up to 8 each):")
    for name, _ in RULES:
        examples = [f["text"] for f in filtered if f["rule"] == name][:8]
        if not examples:
            continue
        lines.append(f"\n-- {name} --")
        for ex in examples:
            lines.append(f"  {ex!r}")

    summary_path.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print(f"\nWrote:\n  {filtered_path}\n  {kept_path}\n  {summary_path}")


if __name__ == "__main__":
    main()