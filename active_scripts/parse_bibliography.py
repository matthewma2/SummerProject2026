"""
segment_bibliography.py
=======================
Segments Church's "A Bibliography of Symbolic Logic" (1984) into
per-author blocks, ready for downstream LLM extraction.

Usage
-----
    python segment_bibliography.py                          # uses bundled PDF path
    python segment_bibliography.py path/to/church.pdf      # explicit path
    python segment_bibliography.py --text path/to/raw.txt  # skip PDF extraction

Outputs
-------
  church_authors.json   – list of author-block dicts (author metadata + raw text)
  church_segments/      – one .txt file per author block (for LLM batching)

Each author-block dict has:
  entry_number   int           – bibliography sequence number (1–547)
  flags          list[str]     – margin annotations found: "A", "C", "*", "**", "†"
  raw_name       str           – author name as it appears in the header
  inline_work    str | None    – text of a single-line work fused onto the header
  raw_block      str           – full raw text of the block (header + all works)
  source_lines   [start, end]  – 1-based line numbers in the extracted text
"""

import re
import sys
import json
import os
import subprocess
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_PDF = Path("/Users/matthewma/Downloads/church1984-a-bibliography-of-symbolic-logic (1).pdf")
OUTPUT_JSON = Path("church_authors.json")
OUTPUT_DIR  = Path("church_segments")

# Lines matching these patterns are document boilerplate, not content
BOILERPLATE_PATTERNS = [
    re.compile(r"https?://doi\.org/"),
    re.compile(r"Published online by Cambridge University Press"),
    re.compile(r"^\s*\f"),          # form-feed / page break
    re.compile(r"^\s*ALONZO CHURCH\s*$"),
    re.compile(r"A BIBLIOGRAPHY OF SYMBOLIC LOGIC"),
]

# Max indent that an author-header line can have.
# Work entries are indented much more deeply (17-24 spaces).
AUTHOR_HEADER_MAX_INDENT = 14

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class AuthorBlock:
    entry_number: int
    flags: list        # e.g. ["A", "*"]
    raw_name: str      # e.g. "JACQUES BERNOULLI and JEAN BERNOULLI"
    inline_work: Optional[str]  # text on same line as author after the name
    raw_block: str     # full text of the block
    source_lines: list # [first_line_1based, last_line_1based]

# ---------------------------------------------------------------------------
# Step 1: Extract raw text from PDF
# ---------------------------------------------------------------------------

def extract_text_from_pdf(pdf_path: Path) -> list[str]:
    """
    Use pdftotext -layout (poppler) to extract text preserving indentation,
    which is crucial for distinguishing author headers from work entries.
    Falls back to pdfplumber if pdftotext is unavailable.
    """
    txt_path = pdf_path.with_suffix(".txt")

    # Try pdftotext first (preserves indentation best)
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), str(txt_path)],
        capture_output=True
    )
    if result.returncode == 0:
        print(f"[info] Extracted text via pdftotext → {txt_path}")
        with open(txt_path, encoding="utf-8", errors="replace") as f:
            return f.readlines()

    # Fallback: pdfplumber
    print("[warn] pdftotext failed, falling back to pdfplumber (layout less reliable)")
    try:
        import pdfplumber
        lines = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines.extend(text.splitlines(keepends=True))
        return lines
    except ImportError:
        sys.exit("[error] Neither pdftotext nor pdfplumber is available. "
                 "Install poppler-utils or: pip install pdfplumber")


def load_text_file(path: Path) -> list[str]:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.readlines()

# ---------------------------------------------------------------------------
# Step 2: Clean boilerplate
# ---------------------------------------------------------------------------

def clean_lines(lines: list[str]) -> list[str]:
    """
    Replace boilerplate lines with blank lines (preserving line numbers).
    Does NOT remove them so that source_lines remain accurate.
    """
    cleaned = []
    for line in lines:
        if any(p.search(line) for p in BOILERPLATE_PATTERNS):
            cleaned.append("\n")
        else:
            cleaned.append(line)
    return cleaned

# ---------------------------------------------------------------------------
# Step 3: Detect author header lines
# ---------------------------------------------------------------------------

# Matches the start of an author header line (after stripping leading whitespace).
#
# Breakdown of the pattern:
#   ^                    – start of stripped line
#   (?P<flags>[AC*†T]+\s*)? – optional margin flags: A, C, *, **, †
#                           (T catches OCR mangling of † as 'T' or 'TT')
#   (?P<num>\d+)         – bibliography number
#   \.                   – literal dot
#   \s+                  – whitespace
#   (?P<name>[A-ZVWXYZ][A-Z\s\.\-\'(),&]+)  – author name (all-caps)
#
# The name pattern requires at least one uppercase letter and allows
# uppercase letters, spaces, dots (initials), hyphens, apostrophes,
# parentheses (alternate name), commas, & (joint authors).
#
# Crucially, lowercase letters immediately after the number.dot means
# it's a work entry (e.g., "9. A theory of probable inference"), not
# an author (e.g., "9. H. W. CLEMM").

AUTHOR_HEADER_RE = re.compile(
    r"^(?P<flags>[AC *†T]+\s*)?"          # optional flags
    r"(?P<num>\d{1,3})"                    # entry number (1–547)
    r"\.\s+"                               # dot + space
    r"(?P<name>"
        r"[A-ZVWXYZ\(\)][A-Z\s\.\-\'(),&\u00C0-\u017E]+"  # name chars
    r")"
    r"(?P<rest>.*)?$",                     # anything after the name
    re.UNICODE
)

# These false-positive names appear in work titles that happen to start
# with a short all-caps word (e.g. "A", "B.", "I.") — filter them out.
_CAPS_BUT_NOT_NAME = re.compile(r"^(A|B\.|I\.|II\.|III\.|IV\.|V\.|VI\.|ON|IN|THE|DER|DIE|DAS)\s")


def parse_author_header(line: str) -> Optional[dict]:
    """
    Given a raw line, determine whether it is an author-header line.
    Returns a dict with keys: num, flags, name, rest — or None.
    """
    indent = len(line) - len(line.lstrip())
    if indent > AUTHOR_HEADER_MAX_INDENT:
        return None

    stripped = line.strip()
    if not stripped:
        return None

    m = AUTHOR_HEADER_RE.match(stripped)
    if not m:
        return None

    name = m.group("name").strip()

    # Reject very short matches that are likely false positives
    if len(name) < 2:
        return None

    # Reject if name looks like the start of a title, not a person
    if _CAPS_BUT_NOT_NAME.match(name):
        return None

    # Normalise flags string
    flags_raw = (m.group("flags") or "").strip()
    flags = _parse_flags(flags_raw)

    return {
        "num":   int(m.group("num")),
        "flags": flags,
        "name":  name,
        "rest":  (m.group("rest") or "").strip(),
    }


def _parse_flags(flags_str: str) -> list:
    """Convert a raw flags string like 'A * ' into ['A', '*']."""
    flags = []
    s = flags_str.replace("**", "§").replace("TT", "†").replace("T", "†")
    for ch in s:
        if ch == "A":   flags.append("A")
        elif ch == "C": flags.append("C")
        elif ch == "*": flags.append("*")
        elif ch == "§": flags.append("**")
        elif ch == "†": flags.append("†")
    return list(dict.fromkeys(flags))  # deduplicate, preserve order


# ---------------------------------------------------------------------------
# Step 4: Segment into author blocks
# ---------------------------------------------------------------------------

def segment(lines: list[str]) -> list[AuthorBlock]:
    """
    Walk through all lines and collect runs of text belonging to each author.
    A new author block starts whenever parse_author_header() succeeds and the
    entry number is greater than the previous one (guards against numbered
    work entries leaking through at low indentation — extremely rare).
    """
    blocks: list[AuthorBlock] = []
    current_header: Optional[dict] = None
    current_start: int = 0
    current_lines: list[str] = []
    last_num: int = 0

    # The very first author (Leibniz, entry 1) has an OCR-mangled header:
    # "TTG. W. v. LEIBNIZ." — handle it as a special case.
    leibniz_re = re.compile(r"^\s*T{1,2}G?\.\s+W\.\s+v\.\s+LEIBNIZ", re.IGNORECASE)

    def flush(end_lineno: int):
        nonlocal current_header, current_lines, current_start
        if current_header is None:
            return
        raw = "".join(current_lines).strip()
        if raw:
            blocks.append(AuthorBlock(
                entry_number = current_header["num"],
                flags        = current_header["flags"],
                raw_name     = current_header["name"],
                inline_work  = current_header["rest"] or None,
                raw_block    = raw,
                source_lines = [current_start, end_lineno],
            ))
        current_header = None
        current_lines  = []
        current_start  = 0

    for lineno, line in enumerate(lines, start=1):

        # --- Check for Leibniz special case (entry 1) ---
        if leibniz_re.match(line):
            flush(lineno - 1)
            last_num = 1
            current_header = {
                "num":   1,
                "flags": _parse_flags(re.match(r"^\s*([TC*†]+)", line.strip()).group(1)
                                      if re.match(r"^\s*[TC*†]", line.strip()) else ""),
                "name":  "G. W. v. LEIBNIZ",
                "rest":  "",
            }
            current_start = lineno
            current_lines = [line]
            continue

        # --- Check for normal author header ---
        parsed = parse_author_header(line)
        if parsed and parsed["num"] > last_num:
            flush(lineno - 1)
            last_num = parsed["num"]
            current_header = parsed
            current_start  = lineno
            current_lines  = [line]
            continue

        # --- Accumulate into current block ---
        if current_header is not None:
            current_lines.append(line)

    # Flush the last block
    flush(len(lines))

    return blocks

# ---------------------------------------------------------------------------
# Step 5: Post-processing and validation
# ---------------------------------------------------------------------------

def validate_and_report(blocks: list[AuthorBlock]) -> None:
    nums = [b.entry_number for b in blocks]
    expected = set(range(1, 548))
    found    = set(nums)
    missing  = sorted(expected - found)
    dupes    = [n for n in nums if nums.count(n) > 1]

    print(f"\n[summary]")
    print(f"  Total author blocks found : {len(blocks)}")
    print(f"  Entry numbers range       : {min(nums)} – {max(nums)}")
    if missing:
        print(f"  Missing entry numbers     : {missing[:20]}{'...' if len(missing) > 20 else ''}")
    else:
        print(f"  Missing entry numbers     : none")
    if dupes:
        print(f"  Duplicate entry numbers   : {sorted(set(dupes))}")
    else:
        print(f"  Duplicate entry numbers   : none")

    # Warn about suspiciously short blocks
    short = [b for b in blocks if len(b.raw_block) < 50]
    if short:
        print(f"  Suspiciously short blocks : {[b.entry_number for b in short]}")


# ---------------------------------------------------------------------------
# Step 6: Write outputs
# ---------------------------------------------------------------------------

def write_json(blocks: list[AuthorBlock], path: Path) -> None:
    data = [asdict(b) for b in blocks]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[output] JSON  → {path}  ({len(data)} entries)")


def write_segments(blocks: list[AuthorBlock], directory: Path) -> None:
    directory.mkdir(exist_ok=True)
    for b in blocks:
        # Zero-padded filename so filesystem sort = bibliography sort
        fname = directory / f"{b.entry_number:04d}_{_safe_name(b.raw_name)}.txt"
        with open(fname, "w", encoding="utf-8") as f:
            f.write(f"=== AUTHOR BLOCK {b.entry_number} ===\n")
            f.write(f"Name  : {b.raw_name}\n")
            f.write(f"Flags : {', '.join(b.flags) if b.flags else 'none'}\n")
            f.write(f"Lines : {b.source_lines[0]}–{b.source_lines[1]}\n")
            f.write("=" * 40 + "\n\n")
            f.write(b.raw_block)
            f.write("\n")
    print(f"[output] Segments → {directory}/  ({len(blocks)} files)")


def _safe_name(name: str) -> str:
    """Turn an author name into a safe filename fragment."""
    safe = re.sub(r"[^A-Za-z0-9]+", "_", name)
    return safe[:50].strip("_")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Parse arguments
    use_text_file = False
    text_file_path = None
    pdf_path = DEFAULT_PDF

    args = sys.argv[1:]
    if args and args[0] == "--text":
        if len(args) < 2:
            sys.exit("Usage: python segment_bibliography.py --text path/to/file.txt")
        use_text_file = True
        text_file_path = Path(args[1])
    elif args:
        pdf_path = Path(args[0])

    # Load text
    if use_text_file:
        print(f"[info] Loading text from {text_file_path}")
        lines = load_text_file(text_file_path)
    else:
        if not pdf_path.exists():
            sys.exit(f"[error] PDF not found: {pdf_path}")
        print(f"[info] Extracting text from {pdf_path}")
        lines = extract_text_from_pdf(pdf_path)

    print(f"[info] Loaded {len(lines)} lines")

    # Clean boilerplate
    lines = clean_lines(lines)

    # Segment
    print("[info] Segmenting into author blocks ...")
    blocks = segment(lines)

    # Validate
    validate_and_report(blocks)

    # Write outputs
    write_json(blocks, OUTPUT_JSON)
    write_segments(blocks, OUTPUT_DIR)

    print("\n[done] Next step: feed each segment in church_segments/ to your LLM extractor.")


if __name__ == "__main__":
    main()