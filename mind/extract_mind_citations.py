import argparse
import json
import re
from pathlib import Path

import pdfplumber


def load_target_names(file_path):
    """Load a list of surname targets from a text file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        print(f"Error: target list file '{file_path}' not found.")
        return []


def load_work_terms(file_path):
    """Load work titles and alternative titles from the works JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            works = json.load(f)
    except FileNotFoundError:
        print(f"Error: works file '{file_path}' not found.")
        return []
    except json.JSONDecodeError as exc:
        print(f"Error: malformed JSON in '{file_path}': {exc}")
        return []

    work_terms = []
    for work_id, work in works.items():
        title = work.get('title')
        if title:
            work_terms.append({
                'term': title,
                'work_id': work_id,
                'match_source': 'work_title',
                'canonical_title': title,
            })

        for alt_title in work.get('alternative_titles', []):
            if alt_title:
                work_terms.append({
                    'term': alt_title,
                    'work_id': work_id,
                    'match_source': 'work_alternative_title',
                    'canonical_title': title,
                })

    return work_terms


def extract_text_from_pdf(pdf_path):
    """Extract text from every page of a PDF into a single string."""
    text_content = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_content.append(page_text)

    return " ".join(text_content)


def find_matches(text, term, window=80):
    """Find every occurrence of a term and return context snippets with fixed windows."""
    snippets = []
    escaped_term = re.escape(term)
    pattern = re.compile(rf'(?<!\w){escaped_term}(?!\w)', flags=re.IGNORECASE)

    for match in pattern.finditer(text):
        start = max(0, match.start() - window)
        end = min(len(text), match.end() + window)
        snippet = text[start:end].replace('\n', ' ')
        snippet = ' '.join(snippet.split())
        prefix = '...' if start > 0 else ''
        suffix = '...' if end < len(text) else ''
        snippets.append(f"{prefix}{snippet}{suffix}")

    return snippets


def extract_matches_from_text(pdf_path, names_file_path, works_file_path, window=80):
    """Extract all name and work-title matches from a PDF text stream."""
    names = load_target_names(names_file_path)
    work_terms = load_work_terms(works_file_path)
    raw_text = extract_text_from_pdf(pdf_path)

    with open("debug_raw_pdf_text.txt", "w", encoding="utf-8") as debug_file:
        debug_file.write(raw_text)

    if not raw_text:
        print('Pipeline aborted: empty PDF text stream.')
        return []

    terms_to_search = []
    terms_to_search.extend(
        {
            'term': name,
            'match_source': 'target_name',
            'work_id': None,
            'canonical_title': None,
        }
        for name in names
    )
    terms_to_search.extend(work_terms)

    print(f"Scanning PDF for {len(terms_to_search)} search terms...")

    results = []
    for term_item in terms_to_search:
        term = term_item['term']
        matches = find_matches(raw_text, term, window=window)
        for snippet in matches:
            results.append({
                'matched_term': term,
                'match_source': term_item['match_source'],
                'work_id': term_item['work_id'],
                'canonical_title': term_item['canonical_title'],
                'snippet': snippet,
            })

    return results


def parse_args():
    parser = argparse.ArgumentParser(description='Extract name and title matches from a PDF.')
    parser.add_argument('--pdf', default='/Users/matthewma/Downloads/Venn-FormsLogicalProposition-1880.pdf', help='Path to the PDF file to scan.')
    parser.add_argument('--names', default='target_surnames.txt', help='Path to the target surname list.')
    parser.add_argument('--works', default='mind/works.json', help='Path to the works JSON file.')
    parser.add_argument('--output', default='extracted_mind_citations.json', help='Path to write the JSON output.')
    parser.add_argument('--window', type=int, default=80, help='Characters before and after each match.')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    pdf_path = Path(args.pdf)
    names_path = Path(args.names)
    works_path = Path(args.works)

    if not pdf_path.exists():
        raise SystemExit(f"PDF file not found: {pdf_path}")
    if not names_path.exists():
        raise SystemExit(f"Names list not found: {names_path}")
    if not works_path.exists():
        raise SystemExit(f"Works file not found: {works_path}")

    extracted = extract_matches_from_text(
        str(pdf_path),
        str(names_path),
        str(works_path),
        window=args.window,
    )

    with open(args.output, 'w', encoding='utf-8') as out_file:
        json.dump(extracted, out_file, indent=2, ensure_ascii=False)

    print(f"Pipeline complete. {len(extracted)} matches written to {args.output}")
