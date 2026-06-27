import json
import re
import unicodedata

def normalize_string(s):
    """Normalize names and titles for flexible comparison: lowercase, remove diacritics and dots."""
    if not s:
        return ""
    # Strip accents/diacritics (e.g., ô -> o, č -> c)
    s = unicodedata.normalize('NFD', s)
    s = "".join([c for c in s if unicodedata.category(c) != 'Mn'])
    s = s.lower().replace(".", "").strip()
    return s

def extract_name_components(name_str):
    """
    Splits a name string into given name tokens and a single surname token.
    Treats spaces and hyphens as delimiters.
    Example: "Austin E. Duncan-Jones" -> givens: ['austin', 'e', 'duncan'], surname: 'jones'
    """
    normalized = normalize_string(name_str)
    tokens = [t for t in re.split(r'[\s\-]+', normalized) if t]
    
    if not tokens:
        return [], ""
        
    surname = tokens[-1]
    given_parts = tokens[:-1]
    return given_parts, surname

def check_givens_match(in_givens, db_givens):
    """
    Validates if the input given parts/initials match the database given parts 
    sequentially as an ordered subsequence.
    """
    if not in_givens:
        return True
        
    db_iter = iter(db_givens)
    for in_part in in_givens:
        matched = False
        for db_part in db_iter:
            # FIX: Bidirectional initial matching. If either side is an initial (length 1), 
            # check if first letters match. Otherwise, require an exact full-string match.
            if len(in_part) == 1 or len(db_part) == 1:
                if in_part[0] == db_part[0]:
                    matched = True
                    break
            else:
                if in_part == db_part:
                    matched = True
                    break
        if not matched:
            return False
            
    return True

def find_best_author_match(input_author, authors_db):
    """
    Looks for a last name match in full_name and alternative_names.
    If the last name matches, it verifies the remaining given names/initials.
    """
    in_givens, in_surname = extract_name_components(input_author)
    if not in_surname:
        return None
        
    for author in authors_db:
        # Gather all possible name variations from the database profile
        db_names = [author.get("full_name", "")] + author.get("alternative_names", [])
        
        # 1. Look for a last name match across full_name and alternative_names
        surname_matched = False
        for name in db_names:
            if not name:
                continue
            _, db_surname = extract_name_components(name)
            if in_surname == db_surname:
                surname_matched = True
                break
                
        # 2. If a last name matches, try matching on the rest
        if surname_matched:
            # Collect all unique given name parts across the entire DB profile
            all_db_givens = []
            for name in db_names:
                if not name:
                    continue
                db_givens, _ = extract_name_components(name)
                for g in db_givens:
                    if g not in all_db_givens:
                        all_db_givens.append(g)
            
            # Verify if the input given components match the DB components sequentially
            if check_givens_match(in_givens, all_db_givens):
                return author["id"]
                
    return None

def resolve_id_collision(base_id, works_db_ids):
    """
    Checks if an ID already exists. Shifts from 'a' -> 'b' -> 'c' ... if collided.
    Handles replacing or appending alphabetical suffix seamlessly.
    """
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
    
    # Pre-build an optimized lookup dictionary using (year, tuple_of_author_ids) -> set of normalized titles
    existing_works_lookup = {}
    for work in works_db:
        year = work.get("year")
        authors_tuple = tuple(work.get("authors", []))
        title_norm = normalize_string(work.get("title", ""))
        
        lookup_key = (year, authors_tuple)
        if lookup_key not in existing_works_lookup:
            existing_works_lookup[lookup_key] = set()
        existing_works_lookup[lookup_key].add(title_norm)
    
    processed_works = []
    missing_authors = set()
    duplicate_count = 0

    for item in input_batch:
        # Task 1: Match and Replace Authors
        resolved_authors = []
        for author_name in item.get("authors", []):
            matched_id = find_best_author_match(author_name, authors_db)
            if matched_id:
                resolved_authors.append(matched_id)
            else:
                if author_name not in missing_authors:
                    print(f"⚠️ Match not found for author: \"{author_name}\"")
                missing_authors.add(author_name)
                # Fallback to the original text name string if not found
                resolved_authors.append(author_name)
        
        # Task 2: Check if entry already exists based on Year, Authors, and Title
        item_year = item.get("year")
        item_authors_tuple = tuple(resolved_authors)
        item_title_norm = normalize_string(item.get("title", ""))
        
        lookup_key = (item_year, item_authors_tuple)
        if lookup_key in existing_works_lookup and item_title_norm in existing_works_lookup[lookup_key]:
            print(f"ℹ️ Skipping duplicate entry (already in database): \"{item.get('title')}\" ({item_year})")
            duplicate_count += 1
            continue
            
        # Task 3: Handle ID Collisions
        new_item = item.copy()
        new_item["authors"] = resolved_authors
        
        old_id = item.get("id")
        unique_id = resolve_id_collision(old_id, existing_works_ids)
        new_item["id"] = unique_id
        existing_works_ids.add(unique_id)
        
        processed_works.append(new_item)

    # Output processed batch results
    with open(output_file_path, 'w', encoding='utf-8') as f:
        json.dump(processed_works, f, indent=2, ensure_ascii=False)
        
    print(f"\n🎉 Processing complete! Saved output to: {output_file_path}")
    if duplicate_count:
        print(f"ℹ️ Total duplicate entries filtered out: {duplicate_count}")
    if missing_authors:
        print(f"❌ Total unmatched authors needing your action: {len(missing_authors)}")

# Run the routine
if __name__ == "__main__":
    process_citations(
        batch_file_path="active_data/new_batch.json", 
        authors_file_path="active_data/authors.json", 
        works_file_path="active_data/works.json", 
        output_file_path="active_data/processed_batch.json"
    )