# ============================================================
# old_scripts/resolve_addendum_authors.py
# Resolve and normalize author names from addendum data.
# ============================================================
import json
import os

def normalize_token(text):
    """
    Lowercase and strip trailing whitespace/punctuation for uniform comparison.
    """
    if not text:
        return ""
    return text.strip().lower()

def parse_name_parts(name_string):
    """
    Extracts the lowercase first initial and last name from a name string.
    """
    parts = name_string.strip().split()
    if not parts:
        return None, None
    
    first_initial = normalize_token(parts[0])[0]
    last_name = normalize_token(parts[-1])
    return first_initial, last_name

def is_heuristic_match(raw_author, db_author_record):
    """
    Evaluates whether the extracted author name matches a database record
    by checking first-initial and last-name alignment across the main full name 
    or any alternative aliases.
    """
    raw_first, raw_last = parse_name_parts(raw_author)
    if not raw_first or not raw_last:
        return False
        
    candidates = [db_author_record.get("full_name", "")]
    candidates.extend(db_author_record.get("alternative_names", []))
    
    for candidate in candidates:
        cand_first, cand_last = parse_name_parts(candidate)
        if not cand_first or not cand_last:
            continue
            
        if raw_last == cand_last and raw_first == cand_first:
            return True
            
    return False

def process_bibliography(authors_file, works_file, output_file):
    """
    Loads bibliography items, maps author strings to database IDs using the heuristic,
    tracks unmatched instances, and exports the final dataset to a new file.
    """
    if not os.path.exists(authors_file) or not os.path.exists(works_file):
        print("Error: Reference source files missing.")
        return

    with open(authors_file, 'r', encoding='utf-8') as f:
        authors_db = json.load(f)
        
    with open(works_file, 'r', encoding='utf-8') as f:
        works_data = json.load(f)

    updated_works = []
    unmatched_authors = set()  # Dedupes tracking names

    for work in works_data:
        resolved_work = dict(work)
        raw_authors = work.get("authors", [])
        resolved_authors = []

        for author in raw_authors:
            matched_id = None
            
            for db_record in authors_db:
                if is_heuristic_match(author, db_record):
                    matched_id = db_record["id"]
                    break
            
            if matched_id:
                resolved_authors.append(matched_id)
            else:
                resolved_authors.append(author)
                unmatched_authors.add(author)  # Append to unmatched list
        
        resolved_work["authors"] = resolved_authors
        updated_works.append(resolved_work)

    # Output clean JSON structure to the new target file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(updated_works, f, indent=2, ensure_ascii=False)
        
    # Terminal summary of missed matches
    print(f"Success: Processed metadata compiled into '{output_file}'.")
    print(f"\n--- UNMATCHED AUTHORS REPORT ---")
    print(f"Total Unique Unmatched Authors Found: {len(unmatched_authors)}")
    print("List of unmatched items:")
    for skipped in sorted(unmatched_authors):
        print(f"  - {skipped}")

if __name__ == "__main__":
    # File targets derived from project architecture
    AUTHORS_DB_PATH = "databases/authors.json"
    WORKS_SOURCE_PATH = "addendum_works.json"
    RESOLVED_OUTPUT_PATH = "resolved_addendum_works.json"

    process_bibliography(AUTHORS_DB_PATH, WORKS_SOURCE_PATH, RESOLVED_OUTPUT_PATH)