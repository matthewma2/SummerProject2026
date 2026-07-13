# ============================================================
# jsl_citations_pipeline/1_strip_internal_refs.py
# Remove internal back-references from citation data.
# ============================================================
"""
1_strip_internal_refs.py
-----------------------
Removes internal back-references from 0_jsl_citations_before_stripping.json.

What counts as internal:
  [N] / Name [N] / [N, p. X]   — numbered bibliography back-refs
  op. cit.                       — always a back-ref in this dataset
  loc. cit.                      — always a back-ref
  ibid. / Ibid.                  — bare page pointers (no real bib info)
  q.v.                           — cross-references

Kept ibid. cases:
  • Has vol. N (YYYY) or vol. N, YYYY  → ibid just stands for journal name
  • Has substantial text before ibid.  → author+title present, real citation

[N] kept when vol+year follows it    → bibliography-list entries (e.g. [1] Title, J., vol. 5 (1930))

Usage:
    python3 1_strip_internal_refs.py [input.json] [output.json]

Defaults:
    input  = jsl_citations_data/0_jsl_citations_before_stripping.json
    output = jsl_citations_data/1_jsl_citations_cleaned.json

A removal log is always written to  jsl_citations_data/1_strip_internal_refs_log.txt
"""

import json
import re
import sys
from pathlib import Path
from collections import defaultdict

# ── helpers ──────────────────────────────────────────────────────────────────

def has_vol_year(ref: str) -> bool:
    """True when ref contains a vol. N (YYYY) or vol. N, YYYY pattern."""
    return bool(re.search(
        r'vol\.?\s*\d+[,\s]*\(?(18|19|20)\d{2}\)?',
        ref, re.IGNORECASE
    ))


def classify(ref: str) -> str:
    """
    Return the removal category, or 'KEEP' if the reference should stay.

    Categories (= reasons for removal):
        bracket_ref   — contains [N] notation without real bib info
        op_cit        — op. cit. back-reference
        loc_cit       — loc. cit. back-reference
        ibid_wrapped  — [ibid.] or (ibid.) at start of string (OCR artifact)
        ibid_bare     — ibid. with no substantial content before it
        qv_ref        — q.v. cross-reference
    """

    # ── Rule 1: bracket notation [N], [N, p.X], (N] (OCR variants) ──────────
    if re.search(r'\[\d+\]|\[\d+[,\s]|\(\d+\]', ref):
        # Exception: these turn out to be numbered bibliography entries
        # when a vol+year follows, e.g. "AUTHOR [1] Title, J., vol. 5 (1930)"
        return 'KEEP' if has_vol_year(ref) else 'bracket_ref'

    # ── Rule 2: q.v. ─────────────────────────────────────────────────────────
    if re.search(r'\bq\.v\.', ref, re.IGNORECASE):
        return 'qv_ref'

    # ── Rule 3: op. cit. (all are back-refs in this dataset) ─────────────────
    if re.search(r'\bop\.?\s*cit\.?', ref, re.IGNORECASE):
        return 'op_cit'

    # ── Rule 4: loc. cit. ────────────────────────────────────────────────────
    if re.search(r'\bloc\.?\s*cit\.?', ref, re.IGNORECASE):
        return 'loc_cit'

    # ── Rule 5: ibid. ────────────────────────────────────────────────────────
    if re.search(r'\bibid\.?', ref, re.IGNORECASE):

        # [ibid...] or (ibid...) at the very start → OCR-wrapped page pointer
        if re.match(r'[\[\(]\s*[Ii]bid', ref):
            return 'ibid_wrapped'

        # Has vol+year → ibid. is standing in for a journal name; real citation
        if has_vol_year(ref):
            return 'KEEP'

        # Inspect what comes before "ibid."
        parts = re.split(r'\s*\[?\(?[Ii]bid\.?\]?\)?', ref, maxsplit=1)
        text_before = parts[0].strip().rstrip(',').strip()

        # Nothing substantial before ibid. → bare page pointer
        if len(text_before) <= 20:
            return 'ibid_bare'

        # Enough text before ibid. to represent an author+title → real citation
        return 'KEEP'

    return 'KEEP'


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('jsl_citations_data/0_jsl_citations_before_stripping.json')
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('jsl_citations_data/1_jsl_citations_cleaned.json')
    log_path = Path('jsl_citations_data/1_strip_internal_refs_log.txt')

    print(f'Reading  {input_path}')
    with open(input_path, encoding='utf-8') as f:
        data = json.load(f)

    total_refs   = 0
    removed_refs = 0
    removals_by_cat = defaultdict(int)
    log_lines = []

    cleaned = []
    for entry in data:
        source = entry.get('source', '?')
        kept   = []
        for ref_obj in entry.get('references', []):
            raw = ref_obj.get('reference', '')
            total_refs += 1
            cat = classify(raw)
            if cat == 'KEEP':
                kept.append(ref_obj)
            else:
                removed_refs += 1
                removals_by_cat[cat] += 1
                log_lines.append(f'[{cat}]  source={source}\n  REF: {raw}\n')
        cleaned.append({'source': source, 'references': kept})

    # Write output
    print(f'Writing  {output_path}')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    # Write log
    print(f'Writing  {log_path}')
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write('=== strip_internal_refs removal log ===\n\n')
        f.write(f'Input  : {input_path}\n')
        f.write(f'Output : {output_path}\n\n')
        f.write(f'Total references   : {total_refs}\n')
        f.write(f'Removed            : {removed_refs}\n')
        f.write(f'Kept               : {total_refs - removed_refs}\n\n')
        f.write('Breakdown by category:\n')
        for cat, n in sorted(removals_by_cat.items()):
            desc = {
                'bracket_ref'  : 'Numbered back-ref  [N] / Name [N] / [N, p.X]',
                'op_cit'       : 'op. cit. reference',
                'loc_cit'      : 'loc. cit. reference',
                'ibid_wrapped' : 'Wrapped ibid  [ibid.] / (ibid.)',
                'ibid_bare'    : 'Bare ibid. page pointer',
                'qv_ref'       : 'q.v. cross-reference',
            }.get(cat, cat)
            f.write(f'  {n:5d}  {desc}\n')
        f.write('\n' + '─' * 70 + '\n\n')
        f.write('\n'.join(log_lines))

    # Print summary
    print()
    print('─' * 55)
    print(f'  Total references : {total_refs}')
    print(f'  Removed          : {removed_refs}')
    print(f'  Kept             : {total_refs - removed_refs}')
    print()
    print('  Breakdown:')
    label = {
        'bracket_ref'  : '[N] back-refs',
        'op_cit'       : 'op. cit.',
        'loc_cit'      : 'loc. cit.',
        'ibid_wrapped' : 'ibid. (wrapped)',
        'ibid_bare'    : 'ibid. (bare page ptr)',
        'qv_ref'       : 'q.v.',
    }
    for cat, n in sorted(removals_by_cat.items()):
        print(f'    {n:5d}  {label.get(cat, cat)}')
    print('─' * 55)
    print(f'  See full removal log: {log_path}')


if __name__ == '__main__':
    main()
