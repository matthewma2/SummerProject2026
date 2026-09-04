#!/usr/bin/env python3
"""Parse long references that begin with a recognizable author name."""

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARSER_PATH = PROJECT_ROOT / "jsl_citations_pipeline" / "7_parse_5a_with_authors.py"
DATA_DIR = PROJECT_ROOT / "jsl_citations_data_2"
LOG_DIR = PROJECT_ROOT / "jsl_citations_pipeline_logs"

INPUT_PATH = DATA_DIR / "8a_with_authors.json"
OUTPUT_PATH = DATA_DIR / "9a_parsed_with_authors.json"
IGNORED_PATH = LOG_DIR / "8a_ignored_with_authors.txt"
ERRORS_PATH = LOG_DIR / "8a_parse_errors.txt"


def load_parser():
    spec = importlib.util.spec_from_file_location("jsl_with_author_parser", PARSER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load parser from {PARSER_PATH}")

    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    return parser


def main() -> None:
    parser = load_parser()
    parser.INPUT_PATH = INPUT_PATH
    parser.OUTPUT_PATH = OUTPUT_PATH
    parser.IGNORED_PATH = IGNORED_PATH
    parser.ERRORS_PATH = ERRORS_PATH
    parser.main()


if __name__ == "__main__":
    main()
