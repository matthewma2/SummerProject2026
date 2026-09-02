# ============================================================
# parse_additions_bibliography.py
# Parse the additions bibliography into structured per-author
# blocks for downstream extraction.
# ============================================================
"""
parse_additions_bibliography.py
===============================
Segments Church's "Additions and Corrections to a Bibliography of Symbolic Logic" 
into per-author blocks, ready for downstream LLM extraction.

Usage
-----
    python parse_additions_bibliography.py                          # uses bundled PDF path
    python parse_additions_bibliography.py path/to/church.pdf       # explicit path
    python parse_additions_bibliography.py --text path/to/raw.txt   # skip PDF extraction

Outputs
-------
  church_additions_authors.json   – list of author-block dicts
  church_additions_segments/      – one .txt file per author block
"""

import re
import sys
import json
import os
import subprocess
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_PDF = Path("/Users/matthewma/Downloads/church1984-additions_and_corrections_to_a_bibliography_of_symbolic_logic.pdf")
OUTPUT_JSON = Path("church_additions_authors.json")
OUTPUT_DIR  = Path("church_additions_segments")

# Boilerplate patterns specific to the additions document
BOILERPLATE_PATTERNS = [
    re.compile(r"https?://doi\.org/"),
    re.compile(r"Published online by Cambridge University Press"),
    re.compile(r"^\s*\f"),          
    re.compile(r"^\s*ALONZO CHURCH\s*$"),
    re.compile(r"ADDITIONS AND CORRECTIONS TO A BIBLIOGRAPHY OF SYMBOLIC LOGIC", re.IGNORECASE),
    re.compile(r"^\s*ADDITIONS AND CORRECTIONS\s*$"),
    re.compile(r"^\s*\d+\s*$"), # Bare page numbers
]

AUTHOR_HEADER_MAX_INDENT = 14

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class AuthorBlock:
    entry_number: str          # String because of fractions/OCR artifacts like "382}"
    flags: list        
    raw_name: str      
    inline_work: Optional[str] 
    raw_block: str     
    source_lines: list 

# ---------------------------------------------------------------------------
# Core Extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(pdf_path: Path) -> list[str]:
    txt_path = pdf_path.with_suffix(".txt")
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), str(txt_path)],
        capture_output=True
    )
    if result.returncode == 0:
        print(f"[info] Extracted text via pdftotext → {txt_path}")
        with open(txt_path, encoding="utf-8", errors="replace") as f:
            return f.readlines()

    print("[warn] pdftotext failed, falling back to pdfplumber")
    try:
        import pdfplumber
        lines = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines.extend(text.splitlines(keepends=True))
        return lines
    except ImportError:
        sys.exit("[error] Install poppler-utils or: pip install pdfplumber")

def load_text_file(path: Path) -> list[str]:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.readlines()

def clean_lines(lines: list[str]) -> list[str]:
    cleaned = []
    for line in lines:
        if any(p.search(line) for p in BOILERPLATE_PATTERNS):
            cleaned.append("\n")
        else:
            cleaned.append(line)
    return cleaned

# ---------------------------------------------------------------------------
# Author Header Detection
# ---------------------------------------------------------------------------

# Modified for the Additions document:
# - Allows 1 to 4 digits + OCR artifacts for fractions ($, }, i, J, 1/2)
# - Allows specific lowercase particles (v., van, de, des, di) and parens
AUTHOR_HEADER_RE = re.compile(
    r"^(?P<flags>[AC *†T]+\s*)?" 
    r"(?P<num>\d{1,4}(?:[$.iJ}]|1/2|1/4|3/4|\.\d+)?)" 
    r"\.\s+"
    r"(?P<name>"
        r"(?:[A-Z\u00C0-\u017E]+[\s\.\-\'()&,]*)+"  
        r"(?:[a-z]{1,4}\.\s+|van\s+|de\s+|des\s+|di\s+)?" 
        r"(?:[A-Z\u00C0-\u017E]+[\s\.\-\'()&,]*)*"
        r"(?:\([A-Za-z\u00C0-\u017E\s\.\-\'(),&]+\))?" 
    r")"
    r"(?P<rest>.*)?$",
    re.UNICODE
)

_CAPS_BUT_NOT_NAME = re.compile(r"^(A|B\.|I\.|II\.|III\.|IV\.|V\.|VI\.|ON|IN|THE|DER|DIE|DAS)\s")

def parse_author_header(line: str) -> Optional[dict]:
    indent = len(line) - len(line.lstrip())
    if indent > AUTHOR_HEADER_MAX_INDENT:
        return None

    stripped = line.strip()
    if not stripped:
        return None

    m = AUTHOR_HEADER_RE.match(stripped)
    if not m:
        return None

    name = m.group("name").strip(" .")

    if len(name) < 2 or _CAPS_BUT_NOT_NAME.match(name):
        return None

    flags_raw = (m.group("flags") or "").strip()
    flags = _parse_flags(flags_raw)

    return {
        "num":   m.group("num"),
        "flags": flags,
        "name":  name,
        "rest":  (m.group("rest") or "").strip(),
    }

def _parse_flags(flags_str: str) -> list:
    flags = []
    s = flags_str.replace("**", "§").replace("TT", "†").replace("T", "†")
    for ch in s:
        if ch == "A":   flags.append("A")
        elif ch == "C": flags.append("C")
        elif ch == "*": flags.append("*")
        elif ch == "§": flags.append("**")
        elif ch == "†": flags.append("†")
    return list(dict.fromkeys(flags))

# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------

def segment(lines: list[str]) -> list[AuthorBlock]:
    blocks: list[AuthorBlock] = []
    current_header: Optional[dict] = None
    current_start: int = 0
    current_lines: list[str] = []

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
        parsed = parse_author_header(line)
        
        # We drop the strict sequential 'last_num' check from the original script 
        # because the 'Additions' document contains non-contiguous fractional entries 
        # (e.g. 70, 701 (OCR for 70.25), 71) that break simple linear progression.
        if parsed:
            flush(lineno - 1)
            current_header = parsed
            current_start  = lineno
            current_lines  = [line]
            continue

        if current_header is not None:
            current_lines.append(line)

    flush(len(lines))
    return blocks

# ---------------------------------------------------------------------------
# Post-Processing
# ---------------------------------------------------------------------------

def validate_and_report(blocks: list[AuthorBlock]) -> None:
    nums = [b.entry_number for b in blocks]
    dupes = [n for n in nums if nums.count(n) > 1]

    print(f"\n[summary]")
    print(f"  Total author blocks found : {len(blocks)}")
    
    # Missing entries check removed entirely for the Additions context
    if dupes:
        print(f"  Duplicate entry numbers   : {sorted(set(dupes))}")
    else:
        print(f"  Duplicate entry numbers   : none")

def write_json(blocks: list[AuthorBlock], path: Path) -> None:
    data = [asdict(b) for b in blocks]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[output] JSON  → {path}  ({len(data)} entries)")

def write_segments(blocks: list[AuthorBlock], directory: Path) -> None:
    directory.mkdir(exist_ok=True)
    for idx, b in enumerate(blocks, start=1):
        # We sort by index because the entry numbers include strings/fractions
        fname = directory / f"seq{idx:04d}_{_safe_name(b.entry_number)}_{_safe_name(b.raw_name)}.txt"
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
    safe = re.sub(r"[^A-Za-z0-9]+", "_", name)
    return safe[:50].strip("_")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    use_text_file = False
    text_file_path = None
    pdf_path = DEFAULT_PDF

    args = sys.argv[1:]
    if args and args[0] == "--text":
        if len(args) < 2:
            sys.exit("Usage: python parse_additions_bibliography.py --text path/to/file.txt")
        use_text_file = True
        text_file_path = Path(args[1])
    elif args:
        pdf_path = Path(args[0])

    if use_text_file:
        print(f"[info] Loading text from {text_file_path}")
        lines = load_text_file(text_file_path)
    else:
        if not pdf_path.exists():
            sys.exit(f"[error] PDF not found: {pdf_path}")
        print(f"[info] Extracting text from {pdf_path}")
        lines = extract_text_from_pdf(pdf_path)

    print(f"[info] Loaded {len(lines)} lines")
    lines = clean_lines(lines)

    print("[info] Segmenting Additions and Corrections into author blocks ...")
    blocks = segment(lines)

    validate_and_report(blocks)

    write_json(blocks, OUTPUT_JSON)
    write_segments(blocks, OUTPUT_DIR)
    print("\n[done] Extraction ready.")

if __name__ == "__main__":
    main()