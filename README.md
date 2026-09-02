# Summer Research Project 2026

This project builds bibliographic datasets and citation data for early logic-related works, with special attention to Alonzo Church's bibliography and references from the Journal of Symbolic Logic.

Start here:

- [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md) explains the repo layout, current data files, scripts, and how to continue the work.
- [PROJECT_CLEANUP_PLAN.md](PROJECT_CLEANUP_PLAN.md) lists proposed renames, redundancies, and safe cleanup batches.
- `databases/` contains the current canonical JSON databases: authors, works, journals, and publishers.
- `jsl_citations_pipeline/` contains the numbered JSL citation-processing pipeline.
- `jsl_citations_data/` contains the numbered inputs and outputs for that pipeline.

Most work should treat `databases/works.json` and `databases/authors.json` as the core data sources, and should treat `old_data/`, `old_scripts/`, and `archive/` as historical unless a handoff note says otherwise.
