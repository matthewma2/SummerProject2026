import json
import os
import re

# --- CONFIGURATION ---
JSTOR_METADATA_FILE = "/Users/matthewma/Downloads/jstor_metadata.jsonl"
JSL_CITATIONS_FILE = "jsl_citations.json"
OUTPUT_FILE = "jsl_citations_resolved.json"

def extract_year_and_author(reference_string):
    """Extracts a 4-digit year and the longest capitalized word as an author hint."""
    year_match = re.search(r'\b(1[89]\d{2})\b', reference_string)
    year = year_match.group(1) if year_match else None
    
    author_match = re.search(r'\b([A-Z]{3,})\b', reference_string)
    author_hint = author_match.group(1).lower() if author_match else None
    
    return year, author_hint

def tokenize_string(s):
    """Splits a string into a set of lower-case alphanumeric words for instant lookup."""
    if s is None:
        return set()
    return set(re.findall(r'\b\w{3,}\b', str(s).lower()))

def load_and_index_jstor_stream(filepath):
    """Streams the real JSTOR JSONL file schema line-by-line using item_id and creators_string."""
    print(f"[*] Streaming and indexing {filepath}... This keeps memory low.")
    index = {}
    count = 0
    
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Could not find your master file: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
                
            try:
                article = json.loads(line)
            except json.JSONDecodeError:
                continue

            # 1. Pull the year from the published_date field
            date_val = article.get("published_date")
            if date_val:
                date_str = str(date_val).strip()
                year_match = re.search(r'\b(1[89]\d{2})\b', date_str) or re.match(r'^(1[89]\d{2})', date_str)
                
                if year_match:
                    clean_year = year_match.group(1)
                    if clean_year not in index:
                        index[clean_year] = []
                    
                    # 2. Extract Title and handle optional field variants
                    title = article.get("title") or article.get("is_part_of") or ""
                    title_tokens = tokenize_string(title)
                    
                    # 3. Process the creators_string into lower-case word tokens to match author hints safely
                    creators_str = article.get("creators_string")
                    creator_words = []
                    if creators_str is not None:
                        creator_words = re.findall(r'\b\w{3,}\b', str(creators_str).lower())
                    
                    # 4. Save using the explicit 'item_id' identifier from your schema
                    index[clean_year].append({
                        "id": article.get("item_id"),
                        "title": title,
                        "title_tokens": title_tokens,
                        "authors": creator_words
                    })
                    count += 1
            
            if line_num % 500000 == 0:
                print(f"    -> Read {line_num} lines... Indexed {count} valid articles.")

    print(f"[✓] Successfully indexed {count} JSTOR articles across {len(index)} years.")
    return index

def main():
    # 1. Build index safely
    try:
        jstor_index = load_and_index_jstor_stream(JSTOR_METADATA_FILE)
    except Exception as e:
        print(f"[!] Critical Error streaming JSTOR file: {e}")
        return

    # 2. Load your JSL raw reference file
    print(f"[*] Loading JSL citations from {JSL_CITATIONS_FILE}...")
    if not os.path.exists(JSL_CITATIONS_FILE):
        print(f"[!] Error: Could not find {JSL_CITATIONS_FILE}")
        return

    with open(JSL_CITATIONS_FILE, 'r', encoding='utf-8') as f:
        jsl_data = json.load(f)

    # 3. Fast-match fields using word intersections
    print("[*] Processing references and resolving graph edges at high speed...")
    resolved_count = 0
    skipped_count = 0
    unresolved_count = 0

    for idx, entry in enumerate(jsl_data):
        for ref_obj in entry.get("references", []):
            raw_ref = ref_obj["reference"]
            
            if re.match(r'^\[\d+\]$', raw_ref.strip()):
                ref_obj["id"] = "LOCAL_ABBREVIATION"
                skipped_count += 1
                continue
            
            year, author_hint = extract_year_and_author(raw_ref)
            
            processed_ref_string = raw_ref
            if "this JOURNAL" in raw_ref:
                processed_ref_string = raw_ref.replace("this JOURNAL", "The Journal of Symbolic Logic")

            ref_tokens = tokenize_string(processed_ref_string)
            matched_uuid = None
            
            if year and year in jstor_index:
                best_overlap_count = 0
                best_match_id = None
                
                for candidate in jstor_index[year]:
                    # Author verification matching constraint
                    if author_hint and not any(author_hint in auth for auth in candidate["authors"]):
                        continue
                    
                    # Compute rapid set overlap
                    overlap = len(ref_tokens.intersection(candidate["title_tokens"]))
                    
                    if overlap > best_overlap_count and overlap >= 2:
                        best_overlap_count = overlap
                        best_match_id = candidate["id"]
                
                matched_uuid = best_match_id

            if matched_uuid:
                ref_obj["id"] = matched_uuid
                resolved_count += 1
            else:
                ref_obj["id"] = "UNRESOLVED_EXTERNAL_OR_BOOK"
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