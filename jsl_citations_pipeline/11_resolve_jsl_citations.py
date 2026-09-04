#!/usr/bin/env python3
"""Resolve cleaned JSL reference strings against the merged works database."""

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MATCHER_PATH = Path(__file__).resolve().parent / "_helpers" / "reference_matcher.py"
DATA_DIR = PROJECT_ROOT / "jsl_citations_data"
LOG_DIR = PROJECT_ROOT / "jsl_citations_pipeline_logs"

WORKS_PATH = DATA_DIR / "11_merged_database.json"
INPUT_PATH = DATA_DIR / "2_jsl_citations_cleaned.json"
OUTPUT_PATH = DATA_DIR / "12_jsl_citations_resolved.json"
RESOLVED_LOG_PATH = LOG_DIR / "12_resolved_references.json"
UNRESOLVED_LOG_PATH = LOG_DIR / "12_unresolved_references.json"


def load_matcher():
    spec = importlib.util.spec_from_file_location("jsl_merged_database_matcher", MATCHER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load matcher from {MATCHER_PATH}")

    matcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(matcher)
    return matcher


def main():
    matcher = load_matcher()
    matcher.WORKS_FILE = str(WORKS_PATH)
    matcher.JSL_CITATIONS_FILE = str(INPUT_PATH)
    matcher.OUTPUT_FILE = str(OUTPUT_PATH)
    matcher.RESOLVED_REFERENCES_FILE = str(RESOLVED_LOG_PATH)
    matcher.UNRESOLVED_REFERENCES_FILE = str(UNRESOLVED_LOG_PATH)
    matcher.main()


if __name__ == "__main__":
    main()
