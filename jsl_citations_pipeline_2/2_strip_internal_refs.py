#!/usr/bin/env python3
"""Strip internal references from the compiled JSL reference-string list."""

import json
import re
from collections import defaultdict
from pathlib import Path


INPUT_PATH = Path("jsl_citations_data_2/2_references_compiled.json")
OUTPUT_PATH = Path("jsl_citations_data_2/3_references_cleaned.json")
LOG_PATH = Path("jsl_citations_data_2/2_strip_internal_refs_log.txt")


def has_vol_year(ref: str) -> bool:
    """True when ref contains a vol. N (YYYY) or vol. N, YYYY pattern."""
    return bool(re.search(
        r"vol\.?\s*\d+[,\s]*\(?(18|19|20)\d{2}\)?",
        ref,
        re.IGNORECASE,
    ))


def classify(ref: str) -> str:
    """
    Return the removal category, or 'KEEP' if the reference should stay.

    Categories:
        bracket_ref   - contains [N] notation without real bib info
        op_cit        - op. cit. back-reference
        loc_cit       - loc. cit. back-reference
        ibid_wrapped  - [ibid.] or (ibid.) at start of string
        ibid_bare     - ibid. with no substantial content before it
        qv_ref        - q.v. cross-reference
    """

    if re.search(r"\[\d+\]|\[\d+[,\s]|\(\d+\]", ref):
        return "KEEP" if has_vol_year(ref) else "bracket_ref"

    if re.search(r"\bq\.v\.", ref, re.IGNORECASE):
        return "qv_ref"

    if re.search(r"\bop\.?\s*cit\.?", ref, re.IGNORECASE):
        return "op_cit"

    if re.search(r"\bloc\.?\s*cit\.?", ref, re.IGNORECASE):
        return "loc_cit"

    if re.search(r"\bibid\.?", ref, re.IGNORECASE):
        if re.match(r"[\[\(]\s*[Ii]bid", ref):
            return "ibid_wrapped"

        if has_vol_year(ref):
            return "KEEP"

        parts = re.split(r"\s*\[?\(?[Ii]bid\.?\]?\)?", ref, maxsplit=1)
        text_before = parts[0].strip().rstrip(",").strip()

        if len(text_before) <= 20:
            return "ibid_bare"

        return "KEEP"

    return "KEEP"


def main() -> None:
    references = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    if not isinstance(references, list):
        raise ValueError(f"Expected a JSON list in {INPUT_PATH}")

    cleaned = []
    removals_by_cat = defaultdict(int)
    removed_refs = []
    skipped = 0

    for ref in references:
        if not isinstance(ref, str):
            skipped += 1
            continue

        cat = classify(ref)
        if cat == "KEEP":
            cleaned.append(ref)
        else:
            removals_by_cat[cat] += 1
            removed_refs.append((cat, ref))

    OUTPUT_PATH.write_text(
        json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with LOG_PATH.open("w", encoding="utf-8") as handle:
        handle.write("=== strip_internal_refs removal log ===\n\n")
        handle.write(f"Input  : {INPUT_PATH}\n")
        handle.write(f"Output : {OUTPUT_PATH}\n\n")
        handle.write(f"Total references   : {len(references)}\n")
        handle.write(f"Removed            : {len(removed_refs)}\n")
        handle.write(f"Kept               : {len(cleaned)}\n")
        handle.write(f"Skipped non-strings: {skipped}\n\n")
        handle.write("Breakdown by category:\n")
        for cat, count in sorted(removals_by_cat.items()):
            handle.write(f"  {count:5d}  {cat}\n")
        handle.write("\n")
        for cat, ref in removed_refs:
            handle.write(f"[{cat}] {ref}\n")

    print(f"Read {len(references)} references from {INPUT_PATH}")
    print(f"Wrote {len(cleaned)} cleaned references to {OUTPUT_PATH}")
    print(f"Removed {len(removed_refs)} internal references")
    if skipped:
        print(f"Skipped {skipped} non-string entries")
    print(f"See removal log: {LOG_PATH}")


if __name__ == "__main__":
    main()
