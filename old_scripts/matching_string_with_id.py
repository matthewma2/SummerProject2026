import json
import re

# --- CONFIGURATION ---
WORKS_FILE = "active_data/works.json"
JSL_CITATIONS_FILE = "active_data/jsl_citations_1936.json"
OUTPUT_FILE = "active_data/jsl_citations_1936_resolved.json"

# Multilingual stop words list to remove noise from titles/citations
STOP_WORDS = {
    # English
    'the', 'and', 'of', 'in', 'for', 'to', 'a', 'an', 'is', 'that', 'on', 'with', 
    'by', 'as', 'at', 'from', 'it', 'its', 'are', 'this', 'not', 'or', 'be',
    # German
    'der', 'die', 'das', 'von', 'zu', 'und', 'in', 'den', 'dem', 'des', 'ein', 'eine',
    # French
    'le', 'la', 'les', 'et', 'un', 'une', 'en', 'dans', 'pour', 'du', 'des', 'par'
}

def tokenize_string(s):
    """Splits a string into a set of lower-case alphanumeric words, filtering out stop words."""
    if not s:
        return set()
    words = re.findall(r'\b\w{3,}\b', str(s).lower())
    return {w for w in words if w not in STOP_WORDS}

def extract_year_and_authors(reference_string):
    """
    Extracts a 4-digit year and all potential author name tokens 
    found prior to the title metadata.
    """
    year_match = re.search(r'\b(1[89]\d{2})\b', reference_string)
    year = int(year_match.group(1)) if year_match else None
    
    # Isolate the author prefix block
    if "," in reference_string:
        author_segment = reference_string.split(",", 1)[0]
    elif year_match:
        author_segment = reference_string.split(year_match.group(1), 1)[0]
    else:
        author_segment = reference_string
        
    # Clean bracketed tokens like local citation numbers [4]
    author_segment = re.sub(r'\[\d+\]', '', author_segment)
    
    # Extract alpha character tokens of valid name length
    author_tokens = re.findall(r'\b[a-zA-Z]{3,}\b', author_segment.lower())
    
    # Filter out residual academic non-names from the author block
    ignored_tokens = {'and', 'von', 'van', 'der', 'the', 'this', 'vol', 'journal', 'review'}
    author_hints = [w for w in author_tokens if w not in ignored_tokens]
    
    return year, author_hints

def build_index(works_data):
    """
    Builds an optimized resolution structure: index[year][author_token] = [works...]
    Incorporates primary and alternative titles.
    """
    index = {}
    for work in works_data:
        year = work.get("year")
        if year is None:
            continue
            
        try:
            year_key = int(year)
        except ValueError:
            continue
            
        if year_key not in index:
            index[year_key] = {}
            
        # Compile all available title tokens
        title_tokens = tokenize_string(work.get("title", ""))
        for alt_title in work.get("alternative_titles", []):
            title_tokens.update(tokenize_string(alt_title))
            
        record = {
            "id": work.get("id"),
            "title_tokens": title_tokens
        }
        
        # Tokenize author fields (splitting hyphens like 'wilbur-john-walkoe-jr')
        author_tokens = set()
        for author in work.get("authors", []):
            words = re.findall(r'\b[a-zA-Z]{3,}\b', author.lower())
            for w in words:
                if w not in {'the', 'cynic', 'von', 'van', 'der', 'and'}:
                    author_tokens.add(w)
                    
        if author_tokens:
            for token in author_tokens:
                if token not in index[year_key]:
                    index[year_key][token] = []
                index[year_key][token].append(record)
        else:
            if "_UNKNOWN_AUTHOR_" not in index[year_key]:
                index[year_key]["_UNKNOWN_AUTHOR_"] = []
            index[year_key]["_UNKNOWN_AUTHOR_"].append(record)
            
    return index

def main():
    print(f"[*] Loading works data from {WORKS_FILE}...")
    with open(WORKS_FILE, 'r', encoding='utf-8') as f:
        works_data = json.load(f)
        
    works_index = build_index(works_data)
    print(f"[✓] Successfully indexed {len(works_data)} works.")
    
    print(f"[*] Loading raw citations from {JSL_CITATIONS_FILE}...")
    with open(JSL_CITATIONS_FILE, 'r', encoding='utf-8') as f:
        jsl_data = json.load(f)
        
    resolved_count = 0
    skipped_count = 0
    unresolved_count = 0

    print("[*] Resolving reference string matches...")
    for entry in jsl_data:
        for ref_obj in entry.get("references", []):
            raw_ref = ref_obj.get("reference", "")
            
            # Skip brief internal or local abbreviations (e.g., "[3]")
            if re.match(r'^\[\d+\]\s*(.*)$', raw_ref.strip()) and len(raw_ref.strip()) < 15:
                ref_obj["id"] = None
                skipped_count += 1
                continue
                
            year, author_hints = extract_year_and_authors(raw_ref)
            
            best_match_id = None
            max_overlap = 0
            is_tie = False
            
            if year and year in works_index:
                year_bucket = works_index[year]
                ref_tokens = tokenize_string(raw_ref)
                
                # Gather all candidate items across any matching author name token
                candidates = {}
                for hint in author_hints:
                    if hint in year_bucket:
                        for candidate in year_bucket[hint]:
                            candidates[candidate["id"]] = candidate
                
                # Evaluate token overlap intersections
                for cand_id, candidate in candidates.items():
                    overlap = len(ref_tokens.intersection(candidate["title_tokens"]))
                    
                    if overlap > max_overlap:
                        max_overlap = overlap
                        best_match_id = cand_id
                        is_tie = False
                    elif overlap == max_overlap and overlap > 0:
                        is_tie = True
            
            # Require high confidence: strict unique match with at least 2 clean overlaps
            if best_match_id and max_overlap >= 2 and not is_tie:
                ref_obj["id"] = best_match_id
                resolved_count += 1
            else:
                ref_obj["id"] = None
                unresolved_count += 1

    print(f"[*] Saving resolved structures to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(jsl_data, f, indent=4, ensure_ascii=False)

    print("\n[✓] Execution Completed Successfully!")
    print(f"    - Matches Resolved (Unique ID Assigned): {resolved_count}")
    print(f"    - Internal Structural Shortcuts Skipped: {skipped_count}")
    print(f"    - Remaining Unresolved Items left as null: {unresolved_count}")

if __name__ == "__main__":
    main()