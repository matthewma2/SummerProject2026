import argparse
import json
import re
from pathlib import Path

import pdfplumber


def load_authors(file_path):
    """Load author full names and alternative names from an authors JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            authors = json.load(f)
    except FileNotFoundError:
        print(f"Error: authors file '{file_path}' not found.")
        return []
    except json.JSONDecodeError as exc:
        print(f"Error: malformed JSON in '{file_path}': {exc}")
        return []

    if not isinstance(authors, list):
        print(f"Error: expected a JSON array in '{file_path}'")
        return []

    def is_first_name_only(term, full_name):
        if not term or not full_name:
            return False

        term_norm = term.strip().lower()
        full_tokens = re.findall(r"\b[\w'-]+\b", full_name.lower())
        return len(full_tokens) > 1 and term_norm == full_tokens[0]

    terms = []
    for author in authors:
        if not isinstance(author, dict):
            continue

        author_id = author.get('id')
        full_name = author.get('full_name') or author.get('name') or ''
        alternative_names = author.get('alternative_names', []) or []

        if full_name:
            terms.append({
                'term': full_name,
                'match_source': 'author_full_name',
                'author_id': author_id,
                'work_id': None,
                'canonical_title': None,
            })

        for alt_name in alternative_names:
            if alt_name and not is_first_name_only(alt_name, full_name):
                terms.append({
                    'term': alt_name,
                    'match_source': 'author_alternative_name',
                    'author_id': author_id,
                    'work_id': None,
                    'canonical_title': None,
                })

    return terms


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
    for work in works:
        title = work.get('title')
        id = work.get('id')
        if title:
            work_terms.append({
                'term': title,
                'work_id': id,
                'match_source': 'work_title',
                'canonical_title': title,
                'year': work.get('year'),
                'author_id': work.get('author'),
            })

        if work.get('alternative_titles') is not None:
            for alt_title in work.get('alternative_titles', []):
                if alt_title:
                    work_terms.append({
                        'term': alt_title,
                        'work_id': id,
                        'match_source': 'work_alternative_title',
                        'canonical_title': title,
                        'year': work.get('year'),
                        'author_id': work.get('author'),
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


def split_sentences(text):
    """Split text into sentences while preserving start/end offsets."""
    sentences = []
    start = 0
    for match in re.finditer(r'(?<=[.!?])\s+', text):
        end = match.end()
        sentence = text[start:end].strip()
        if sentence:
            sentences.append((start, end, sentence))
        start = end

    if start < len(text):
        sentence = text[start:].strip()
        if sentence:
            sentences.append((start, len(text), sentence))

    if not sentences and text.strip():
        sentences.append((0, len(text), text.strip()))

    return sentences


def find_matches(text, term, window=80, require_capitalized_start=False):
    """Find every occurrence of a term and return snippets containing nearby sentences."""
    snippets = []
    escaped_term = re.escape(term)
    pattern = re.compile(rf'(?<!\w){escaped_term}(?!\w)', flags=re.IGNORECASE)
    sentence_spans = split_sentences(text)

    for match in pattern.finditer(text):
        if require_capitalized_start:
            first_char = text[match.start()]
            if not first_char.isupper():
                continue

        # Locate the sentence containing the match
        sentence_index = None
        for idx, (sent_start, sent_end, _) in enumerate(sentence_spans):
            if sent_start <= match.start() < sent_end:
                sentence_index = idx
                break

        if sentence_index is None:
            continue

        selected = []
        if sentence_index > 0:
            selected.append(sentence_spans[sentence_index - 1][2])
        selected.append(sentence_spans[sentence_index][2])
        if sentence_index + 1 < len(sentence_spans):
            selected.append(sentence_spans[sentence_index + 1][2])

        snippet = ' '.join(s.replace('\n', ' ') for s in selected)
        snippet = ' '.join(snippet.split())
        sentence_start = sentence_spans[sentence_index][0]
        sentence_end = sentence_spans[sentence_index][1]
        prefix = '...' if sentence_start > 0 else ''
        suffix = '...' if sentence_end < len(text) else ''
        snippets.append(f"{prefix}{snippet}{suffix}")

    return snippets


def collect_years(snippet):
    """Extract any 3- or 4-digit years from a snippet."""
    year_pattern = re.compile(r'\b-?\d{3,4}\b')
    return sorted({int(match.group(0)) for match in year_pattern.finditer(snippet)})


def find_work_references(snippet, work_terms):
    """Detect matching work titles or alternative titles inside a snippet."""
    references = []
    for term_item in work_terms:
        escaped_term = re.escape(term_item['term'])
        pattern = re.compile(rf'(?<!\w){escaped_term}(?!\w)', flags=re.IGNORECASE)
        if pattern.search(snippet):
            references.append({
                'work_id': term_item['work_id'],
                'matched_term': term_item['term'],
                'canonical_title': term_item['canonical_title'],
            })
    return references


def extract_matches_from_text(pdf_path, authors_file_path, works_file_path, window=80):
    """Extract all author name matches from a PDF text stream and then find work references in each snippet."""
    authors = load_authors(authors_file_path)
    work_terms = load_work_terms(works_file_path)
    raw_text = extract_text_from_pdf(pdf_path)

    if not raw_text:
        print('Pipeline aborted: empty PDF text stream.')
        return []

    terms_to_search = list(authors)

    print(f"Scanning PDF for {len(terms_to_search)} author search terms...")

    results = []
    for term_item in terms_to_search:
        term = term_item['term']
        matches = find_matches(raw_text, term, window=window, require_capitalized_start=True)
        for snippet in matches:
            related_works = find_work_references(snippet, work_terms)
            if related_works:
                result = {
                    'matched_term': term,
                    'matched_author': term_item.get('author_id'),
                    'snippet': snippet,
                    'matched_works': related_works,
                }
                results.append(result)

    return results


def parse_args():
    parser = argparse.ArgumentParser(description='Extract name and title matches from a PDF.')
    parser.add_argument('--pdf', default='/Users/matthewma/Downloads/Chadwick-LogicalConstants-1927.pdf', help='Path to the PDF file to scan.')
    parser.add_argument('--authors', default='active_data/authors.json', help='Path to the authors JSON file.')
    parser.add_argument('--works', default='active_data/works.json', help='Path to the works JSON file.')
    parser.add_argument('--output', default='active_data/extracted_mind_citations.json', help='Path to write the JSON output.')
    parser.add_argument('--window', type=int, default=80, help='Characters before and after each match.')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    pdf_path = Path(args.pdf)
    authors_path = Path(args.authors)
    works_path = Path(args.works)

    if not pdf_path.exists():
        raise SystemExit(f"PDF file not found: {pdf_path}")
    if not authors_path.exists():
        raise SystemExit(f"Authors file not found: {authors_path}")
    if not works_path.exists():
        raise SystemExit(f"Works file not found: {works_path}")

    extracted = extract_matches_from_text(
        str(pdf_path),
        str(authors_path),
        str(works_path),
        window=args.window,
    )

    with open(args.output, 'w', encoding='utf-8') as out_file:
        json.dump(extracted, out_file, indent=2, ensure_ascii=False)

    print(f"Pipeline complete. {len(extracted)} matches written to {args.output}")
