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
SUMMARY_LOG_PATH = LOG_DIR / "12_resolution_summary.json"


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
    matcher.EXISTING_MATCHES_FILE = str(LOG_DIR / "9_existing_works_matched.json")
    matcher.READY_AUDIT_FILE = str(LOG_DIR / "9_works_ready_to_add_audit.json")
    matcher.MERGE_LOG_FILE = str(LOG_DIR / "10_merge_works_database_log.json")
    matcher.PARSED_DUPLICATES_FILE = str(LOG_DIR / "9_parsed_duplicates.json")
    matcher.CLASSIFIED_REFERENCES_FILE = str(LOG_DIR / "8b_classified.json")
    matcher.REFERENCE_STATUS_FILES = {
        "internal": str(LOG_DIR / "6b_further_internal_refs.json"),
        "contextual": str(LOG_DIR / "6b_journal_refs.json"),
        "unresolved": str(LOG_DIR / "8b_unresolved_after_parse.json"),
        "contextual_or_fragment": str(LOG_DIR / "9_invalid_or_contextual_references.json"),
    }
    matcher.RESOLUTION_SUMMARY_FILE = str(SUMMARY_LOG_PATH)
    matcher.main()


if __name__ == "__main__":
    main()
