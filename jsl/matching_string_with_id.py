import json
import os
import re

# --- CONFIGURATION ---
JSTOR_METADATA_FILE = "/Users/matthewma/Downloads/jstor_metadata.jsonl"
JSL_CITATIONS_FILE = "jsl_citations.json"
OUTPUT_FILE = "jsl_citations_resolved.json"

def extract_author_from_reference(reference_string):
    """Extracts the author name(s) from the beginning of a reference string.
    
    Common patterns:
    - "LASTNAME, FIRSTNAME" or "LASTNAME and FIRSTNAME"
    - Multiple authors separated by commas or 'and'
    """
    # Try pattern: "LASTNAME, FIRSTNAME," or "LASTNAME and FIRSTNAME,"
    author_pattern = r'^([A-Z][A-Za-z\s,\.&\-]*?)[,\.]'
    match = re.match(author_pattern, reference_string.strip())
    
    if match:
        author_text = match.group(1).strip()
        # Extract just the last names
        names = re.findall(r'[A-Z][a-z]+', author_text)
        return names if names else [author_text.lower()]
    
    return []

def extract_title_from_reference(reference_string):
    """Extracts the title from a reference string.
    
    Handles various patterns:
    - Author, "Title". Journal
    - Author, Title. Journal
    - "Title of Work" ... Journal
    - Title before (year) or vol.
    """
    ref = reference_string.strip()
    
    # Pattern 1: Quoted title "Title of Work"
    quoted = re.search(r'"([^"]{5,})"', ref)
    if quoted:
        return quoted.group(1).strip()
    
    # Pattern 2: Author, Title. Journal (extract what's between comma and period/Journal)
    # This handles: "Smith, A wonderful paper on logic. Mind, vol. 10"
    author_title_pattern = r'^[^,]+,\s+([^\.]+?)\s*(?:\.|$|this JOURNAL|Mind|Journal of|vol\.|pp\.)'
    match = re.search(author_title_pattern, ref, re.IGNORECASE)
    if match:
        title = match.group(1).strip()
        # Filter out very short matches that are probably not titles
        if len(title) > 8 and not re.match(r'^\d{3,}$', title):
            return title
    
    # Pattern 3: Title before journal name or volume
    # Extract everything before "Mind," "Journal," "vol.", "pp.", "(1...", "[1...]"
    journal_start = re.search(
        r'(this JOURNAL|Mind[,\.]|Journal of|vol\.|pp\.|in |Proceedings|Chapter|\(\d{4})', 
        ref, 
        re.IGNORECASE
    )
    if journal_start:
        # Get the part before journal reference
        before_journal = ref[:journal_start.start()].strip()
        # Remove author prefix (everything before first comma if there's a comma)
        comma_idx = before_journal.rfind(',')
        if comma_idx > 0:
            potential_title = before_journal[comma_idx+1:].strip()
            if len(potential_title) > 8:
                return potential_title
    
    return None

def extract_year_from_reference(reference_string):
    """Extracts a 4-digit year from reference string."""
    year_match = re.search(r'\b(1[89]\d{2})\b', reference_string)
    return year_match.group(1) if year_match else None

def normalize_title(title):
    """Normalize title for comparison: lowercase, remove extra whitespace."""
    if not title:
        return ""
    return re.sub(r'\s+', ' ', title.lower().strip())

def load_and_index_jstor_stream(filepath):
    """Streams the JSTOR JSONL file and indexes by author and title for exact matching.
    
    Optimized for memory efficiency and speed.
    """
    print(f"[*] Streaming and indexing {filepath}...")
    
    # Index structure: {(author_lastname, title_normalized): id}
    # This is more memory efficient than storing all author variants
    title_index = {}
    count = 0
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Could not find: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
                
            try:
                article = json.loads(line)
            except json.JSONDecodeError:
                continue

            title = article.get("title") or article.get("is_part_of")
            creators_str = article.get("creators_string")
            item_id = article.get("item_id")
            
            if not title or not creators_str or not item_id:
                continue
            
            # Extract author last names from creators_string
            author_names = re.findall(r'\b([A-Z][a-z]+)\b', str(creators_str))
            
            if author_names:
                title_normalized = normalize_title(title)
                
                # Store with each author as key for fast lookup
                for author in author_names:
                    author_lower = author.lower()
                    key = (author_lower, title_normalized)
                    
                    # Only store first match for each author-title combination
                    if key not in title_index:
                        title_index[key] = item_id
                        count += 1
            
            if line_num % 1000000 == 0:
                print(f"    -> Read {line_num} lines... Indexed {len(title_index)} author-title pairs.")

    print(f"[✓] Successfully indexed {len(title_index)} author-title pairs from JSTOR metadata.")
    return title_index

def find_match_by_author_and_title(ref_string, title_index):
    """Find a match by extracting author and title, then doing exact matching.
    
    Returns:
        - id if exact match found
        - None if no match
    """
    authors = extract_author_from_reference(ref_string)
    title = extract_title_from_reference(ref_string)
    
    if not authors or not title:
        return None
    
    title_normalized = normalize_title(title)
    
    # Try each author from the reference
    for author_name in authors:
        author_lower = author_name.lower()
        key = (author_lower, title_normalized)
        
        # Direct exact match lookup (O(1))
        if key in title_index:
            return title_index[key]
    
    return None

def main():
    # 1. Build title index
    try:
        title_index = load_and_index_jstor_stream(JSTOR_METADATA_FILE)
    except Exception as e:
        print(f"[!] Critical Error: {e}")
        return

    # 2. Load JSL citations
    print(f"[*] Loading JSL citations from {JSL_CITATIONS_FILE}...")
    if not os.path.exists(JSL_CITATIONS_FILE):
        print(f"[!] Error: Could not find {JSL_CITATIONS_FILE}")
        return

    with open(JSL_CITATIONS_FILE, 'r', encoding='utf-8') as f:
        jsl_data = json.load(f)

    # 3. Process and resolve references
    print("[*] Processing references and matching against JSTOR metadata...")
    resolved_count = 0
    skipped_count = 0
    unresolved_count = 0

    for idx, entry in enumerate(jsl_data):
        for ref_obj in entry.get("references", []):
            raw_ref = ref_obj["reference"]
            
            # Skip reference-only citations (e.g., "[3]")
            if re.match(r'^\[\d+\]$', raw_ref.strip()):
                ref_obj["id"] = "LOCAL_ABBREVIATION"
                skipped_count += 1
                continue
            
            # Try to find a match
            matched_id = find_match_by_author_and_title(raw_ref, title_index)
            
            if matched_id:
                ref_obj["id"] = matched_id
                resolved_count += 1
            else:
                ref_obj["id"] = None
                unresolved_count += 1
        
        if (idx + 1) % 1000 == 0:
            print(f"    Processed {idx + 1}/{len(jsl_data)} citation packages...")

    # 4. Save results
    print(f"[*] Writing updated data to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(jsl_data, f, indent=4, ensure_ascii=False)

    print("\n[✓] Run Completed Successfully!")
    print(f"    - Matches Resolved (IDs inserted): {resolved_count}")
    print(f"    - Internal Abbreviations Skipped: {skipped_count}")
    print(f"    - Unresolved/Books: {unresolved_count}")

if __name__ == "__main__":
    main()