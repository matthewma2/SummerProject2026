import json
import re
import unicodedata

def normalize_string(s):
    """Normalize names for flexible comparison: lowercase, remove diacritics and dots."""
    if not s:
        return ""
    # Strip accents/diacritics (e.g., ô -> o, č -> c)
    s = unicodedata.normalize('NFD', s)
    s = "".join([c for c in s if unicodedata.category(c) != 'Mn'])
    s = s.lower().replace(".", "").strip()
    return s

def extract_name_components(name_str):
    """
    Splits a full name or initials-based name into initials and surname tokens.
    Example: "Alfred Cyril Ewing" -> initials: ['a', 'c'], surname: 'ewing'
             "A. A. Hinčin" -> initials: ['a', 'a'], surname: 'hincin'
    """
    normalized = normalize_string(name_str)
    tokens = [t for t in re.split(r'[\s\-]+', normalized) if t]
    
    if not tokens:
        return [], ""
        
    # Surnames are usually the last part
    surname = tokens[-1]
    given_parts = tokens[:-1]
    
    # Extract first letter of each given name part as initials
    initials = [part[0] for part in given_parts if part]
    return initials, surname

def find_best_author_match(input_author, authors_db):
    """
    Validates an author if their surname matches the DB record's full name/aliases,
    and their given initials match sequentially.
    """
    in_initials, in_surname = extract_name_components(input_author)
    
    for author in authors_db:
        # 1. Gather all possible surname candidates from the database record
        db_names = [author.get("full_name", "")] + author.get("alternative_names", [])
        db_surnames = [extract_name_components(n)[1] for n in db_names if n]
        
        # Check if the input surname is recognized in the database profile
        if in_surname in db_surnames:
            # 2. Check initials matching (if the input provided any given names/initials)
            db_main_initials, _ = extract_name_components(author.get("full_name", ""))
            
            # If input has initials, verify they match sequentially with the DB record
            if in_initials and db_main_initials:
                # Truncate to compare up to the length of whichever sequence is shorter
                min_len = min(len(in_initials), len(db_main_initials))
                if in_initials[:min_len] == db_main_initials[:min_len]:
                    return author["id"]
            else:
                # If either side lacks initials (e.g., just a surname query), match on surname
                return author["id"]
                
    return None

def resolve_id_collision(base_id, works_db_ids):
    """
    Checks if an ID already exists. Shiftts from 'a' -> 'b' -> 'c' ... if collided.
    Handles replacing or appending alphabetical suffix seamlessly.
    """
    # Parse out the trailing alpha character sequence if it follows a year (e.g., Tarski1936a -> suffix 'a')
    match = re.match(r"^([a-zA-Z0-9\-]+?\d{4})([a-z]*)$", base_id)
    if match:
        prefix, suffix = match.groups()
    else:
        prefix, suffix = base_id, ""

    current_suffix = suffix if suffix else "a"
    
    while True:
        candidate_id = f"{prefix}{current_suffix}"
        if candidate_id not in works_db_ids:
            return candidate_id
        
        # Increment alphabetical suffix: 'a' -> 'b', ..., 'z' -> 'aa'
        # Base-26 conversion algorithm to increment string counters
        num = 0
        for char in current_suffix:
            num = num * 26 + (ord(char) - ord('a') + 1)
        num += 1
        
        new_suffix = ""
        while num > 0:
            num, remainder = divmod(num - 1, 26)
            new_suffix = chr(ord('a') + remainder) + new_suffix
        current_suffix = new_suffix

def process_citations(batch_file_path, authors_file_path, works_file_path, output_file_path):
    # Load Databases
    with open(authors_file_path, 'r', encoding='utf-8') as f:
        authors_db = json.load(f)
    with open(works_file_path, 'r', encoding='utf-8') as f:
        works_db = json.load(f)
    with open(batch_file_path, 'r', encoding='utf-8') as f:
        input_batch = json.load(f)

    # Set of existing IDs in works database for O(1) loop checks
    existing_works_ids = {work["id"] for work in works_db}
    
    processed_works = []
    missing_authors = set()

    for item in input_batch:
        new_item = item.copy()
        
        # Task 1: Handle ID Collisions
        old_id = item.get("id")
        unique_id = resolve_id_collision(old_id, existing_works_ids)
        new_item["id"] = unique_id
        # Reserve it immediately so subsequent entries in the same batch don't steal it
        existing_works_ids.add(unique_id)
        
        # Task 2: Match and Replace Authors
        resolved_authors = []
        for author_name in item.get("authors", []):
            matched_id = find_best_author_match(author_name, authors_db)
            if matched_id:
                resolved_authors.append(matched_id)
            else:
                print(f"⚠️ Match not found for author: \"{author_name}\"")
                missing_authors.add(author_name)
                # Fallback to the original text name string if not found
                resolved_authors.append(author_name)
                
        new_item["authors"] = resolved_authors
        processed_works.append(new_item)

    # Output processed batch results
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(processed_works, f, indent=2, ensure_ascii=False)
        
    print(f"\n🎉 Processing complete! Saved output to: {output_file_path}")
    if missing_authors:
        print(f"❌ Total unmatched authors needing your action: {len(missing_authors)}")

# Run the routine
if __name__ == "__main__":
    # Specify your file names here
    process_citations(
        batch_file_path="active_data/new_batch.json", 
        authors_file_path="active_data/authors.json", 
        works_file_path="active_data/works.json", 
        output_file_path="active_data/processed_batch.json"
    )