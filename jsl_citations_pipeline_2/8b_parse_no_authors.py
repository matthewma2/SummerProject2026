#!/usr/bin/env python3
"""Recover, parse, and classify long references without detected authors."""

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARSER_PATH = PROJECT_ROOT / "jsl_citations_pipeline" / "8_parse_5b_no_authors.py"
DATA_DIR = PROJECT_ROOT / "jsl_citations_data_2"
LOG_DIR = PROJECT_ROOT / "jsl_citations_pipeline_logs"

INPUT_PATH = DATA_DIR / "8b_no_authors.json"
PARSED_PATH = DATA_DIR / "parsed_no_authors.json"
CLASSIFIED_PATH = LOG_DIR / "8b_classified.json"
CONTEXTUAL_PATH = LOG_DIR / "8b_contextual_references.json"
FRAGMENTS_PATH = LOG_DIR / "8b_fragments.json"
UNRESOLVED_PATH = LOG_DIR / "8b_unresolved_after_parse.json"
ERRORS_PATH = LOG_DIR / "8b_parse_errors.txt"


def load_parser():
    spec = importlib.util.spec_from_file_location("jsl_no_author_parser", PARSER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load parser from {PARSER_PATH}")

    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    return parser


def main() -> None:
    parser = load_parser()
    parser.INPUT_PATH = INPUT_PATH
    parser.PARSED_PATH = PARSED_PATH
    parser.CLASSIFIED_PATH = CLASSIFIED_PATH
    parser.CONTEXTUAL_PATH = CONTEXTUAL_PATH
    parser.FRAGMENTS_PATH = FRAGMENTS_PATH
    parser.UNRESOLVED_PATH = UNRESOLVED_PATH
    parser.ERRORS_PATH = ERRORS_PATH
    parser.main()


if __name__ == "__main__":
    main()
