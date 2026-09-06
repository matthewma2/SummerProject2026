#!/usr/bin/env python3
"""Parse all-caps-author references into structured bibliographic records."""

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARSER_PATH = Path(__file__).resolve().parent / "_helpers" / "unresolved_parser.py"
DATA_DIR = PROJECT_ROOT / "jsl_citations_data"
LOG_DIR = PROJECT_ROOT / "jsl_citations_pipeline_logs"

INPUT_PATH = DATA_DIR / "6a_all_caps_author_references.json"
PARSED_PATH = DATA_DIR / "parsed_all_caps_author_references.json"
IGNORED_PATH = LOG_DIR / "6a_ignored_all_caps_author_references.txt"
ERRORS_PATH = DATA_DIR / "all_caps_parse_errors.txt"


def load_parser():
    """Load the shared unresolved-reference parser from the first pipeline."""
    spec = importlib.util.spec_from_file_location("jsl_unresolved_parser", PARSER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load parser from {PARSER_PATH}")

    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    return parser


def main() -> None:
    parser = load_parser()
    parser.parse_file(
        INPUT_PATH,
        PARSED_PATH,
        IGNORED_PATH,
        ERRORS_PATH,
        include_raw_reference=True,
    )


if __name__ == "__main__":
    main()
