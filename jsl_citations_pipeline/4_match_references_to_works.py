#!/usr/bin/env python3
"""Match cleaned JSL reference strings against databases/works.json."""

import importlib.util
import json
from pathlib import Path


MATCHER_PATH = Path(__file__).resolve().parent / "_helpers" / "reference_matcher.py"
WORKS_PATH = Path("databases/works.json")
INPUT_PATH = Path("jsl_citations_data/4_references_deduplicated.json")
UNRESOLVED_PATH = Path("jsl_citations_data/5_unresolved_references.json")
RESOLVED_LOG_PATH = Path("jsl_citations_pipeline_logs/5_resolved_references_log.json")


def load_matcher():
    spec = importlib.util.spec_from_file_location("jsl_reference_matcher", MATCHER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load matcher from {MATCHER_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    matcher = load_matcher()

    works = json.loads(WORKS_PATH.read_text(encoding="utf-8"))
    references = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    if not isinstance(references, list):
        raise ValueError(f"Expected a JSON list in {INPUT_PATH}")

    works_index = matcher.build_year_index(works)
    author_index = matcher.build_author_index(works)

    resolved = []
    unresolved = []
    skipped = 0

    for ref in references:
        if not isinstance(ref, str) or not ref.strip():
            skipped += 1
            continue

        resolved_id, ok = matcher.resolve_reference(ref, works_index, author_index)
        if ok:
            resolved.append({
                "reference": ref,
                "id": resolved_id,
            })
        else:
            unresolved.append(ref)

    UNRESOLVED_PATH.write_text(
        json.dumps(unresolved, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    RESOLVED_LOG_PATH.write_text(
        json.dumps(resolved, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Loaded {len(works)} works from {WORKS_PATH}")
    print(f"Read {len(references)} references from {INPUT_PATH}")
    print(f"Resolved {len(resolved)} references")
    print(f"Wrote {len(unresolved)} unresolved references to {UNRESOLVED_PATH}")
    print(f"Wrote resolved-reference log to {RESOLVED_LOG_PATH}")
    if skipped:
        print(f"Skipped {skipped} malformed or empty reference entries")


if __name__ == "__main__":
    main()
