# JSL Citation Statistics

This is a living snapshot of the resolved Journal of Symbolic Logic citation data. Update it after changes to work-ID merging, duplicate-work handling, or final citation resolution—especially after rerunning stages 10 or 11 of the JSL citation pipeline.

Last updated: 2026-09-09

## Data Sources

- Resolved citations: `jsl_citations_data/12_jsl_citations_resolved.json`
- Work metadata: `jsl_citations_data/11_merged_database.json`
- Resolution summary: `jsl_citations_pipeline_logs/12_resolution_summary.json`

Each mention is one resolved reference occurrence. “Source articles” counts distinct JSL source records containing that work ID.

## Resolution Overview

- Extracted reference occurrences: 5,716
- Resolved reference occurrences: 4,197 (73.4%)
- Distinct cited work IDs: 1,959
- Work IDs mentioned exactly once: 1,244
- References without a work ID: 1,519
- Genuinely unresolved references: 879
- Classified contextual references: 369
- Classified internal references: 229
- Classified fragments: 42

## Most-Mentioned Work IDs

| Rank | Work ID | Mentions | Source articles | Year | Work |
|---:|---|---:|---:|---:|---|
| 1 | `BernaysHilbert1934a` | 65 | 57 | 1934 | *Grundlagen der Mathematik. Vol. 1* |
| 2 | `Godel1931a` | 48 | 47 | 1931 | *Uber formal unentscheidbare Satze der Principia Mathematica und verwandter Systeme I* |
| 3 | `Kleene1952a` | 31 | 31 | 1952 | *Introduction to Metamathematics, New York, 1952* |
| 4 | `LukasiewiczTarski1930a` | 23 | 22 | 1930 | *Untersuchungen über den Aussagenkalkül* |
| 5 | `Henkin1949b` | 23 | 23 | 1949 | *The Completeness of the First-Order Functional Calculus* |
| 6 | `Godel1930b` | 21 | 20 | 1930 | *Die Vollstandigkeit der Axiome des logischen Funktionenkalkiils* |
| 7 | `Kleene1952b` | 21 | 21 | 1952 | *Introduction to metamathematics (Amsterdam:* |
| 8 | `Mckinsey1941a` | 20 | 20 | 1941 | *A Solution of the Decision Problem for the Lewis systems S2 and S4, with an Application to Topology* |
| 9 | `Lewis1932b` | 20 | 20 | 1932 | *Symbolic logic (New York and London, 1932)* |
| 10 | `Gentzen1934a` | 19 | 19 | 1934 | *Untersuchungen ilber das logische Schliessen* |
| 11 | `Bernays1937a` | 19 | 10 | 1937 | *A System of Axiomatic Set Theory--Part I* |
| 12 | `MckinseyTarski1948a` | 18 | 18 | 1948 | *Some Theorems About the Sentential Calculi of Lewis and Heyting* |
| 13 | `Godel1940a` | 18 | 18 | 1940 | *The consistency of the continuum hypothesis* |
| 14 | `Spector1955a` | 18 | 18 | 1955 | *Recursive Well-Orderings* |
| 15 | `Church1956a` | 17 | 17 | 1956 | *Introduction to Mathematical Logic* |
| 16 | `Parry1939a` | 17 | 17 | 1939 | *Modalities in the Survey System of Strict Implication* |
| 17 | `Tarski1936e` | 17 | 17 | 1936 | *Der Wahrheitsbegriff in den formalisierten Sprachen* |
| 18 | `Quine1937d` | 17 | 17 | 1937 | *New foundations for mathematical logic* |
| 19 | `Henkin1950a` | 15 | 15 | 1950 | *Completeness in the Theory of Types* |
| 20 | `Kleene1955a` | 15 | 15 | 1955 | *Arithmetical predicates and function quantifiers* |

The top ten IDs account for 291 citations, or 6.9% of resolved citation occurrences.

## Latest Authority-File Improvement

On 2026-09-07, 38 recurring authors absent from `databases/authors.json` were added, and exact citation-form aliases were added to six existing author records. Author matching was also taught to remove a trailing parenthesized publication year from an otherwise valid name. Stages 9–11 were then rerun. Compared with the preceding snapshot, this produced 235 net additional resolved citations, reduced works needing review from 1,046 to 827, and reduced genuinely unresolved references from 1,112 to 879. Ambiguous names, parser debris, uncertain one-off initials, and unverified identities were deliberately left for later review.

## Interpretation Caveat

These are rankings by ID, not necessarily by intellectual work. Duplicate records and separate edition records can divide a work's citations among several IDs. For example, `Kleene1952a` and `Kleene1952b` both represent forms of *Introduction to Metamathematics*. Together they receive 51 mentions, which would place the combined work second in this ranking if they are determined to be duplicates and merged.

Do not combine counts merely because titles look similar. Confirm authorship, edition relationships, publication year, and other metadata before redirecting IDs, then rerun stages 10 and 11 and refresh this report.

## Refresh Checklist

When this report needs updating:

1. Rerun `jsl_citations_pipeline/10_merge_works_database.py` when candidate or duplicate-work decisions have changed.
2. Rerun `jsl_citations_pipeline/11_resolve_jsl_citations.py`.
3. Recount resolved IDs in `12_jsl_citations_resolved.json`.
4. Join those IDs to `11_merged_database.json` for titles and years.
5. Recount distinct source articles for each ID.
6. Update the date, overview, ranking, concentration statistic, and duplicate-work caveats above.
