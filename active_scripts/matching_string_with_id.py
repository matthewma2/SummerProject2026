import json
import os
import pickle
import re

# --- CONFIGURATION ---
JSTOR_METADATA_FILE = "/Users/matthewma/Downloads/jstor_metadata.jsonl"
JSL_CITATIONS_FILE = "jsl_citations.json"
OUTPUT_FILE = "jsl_citations_resolved.json"
CACHE_FILE = "jstor_index_cache.pkl"

def extract_year_and_author(reference_string):
    """
    Extracts a 4-digit year and the last word right before the first comma 
    (typically the surname) as an author hint.
    """
    year_match = re.search(r'\b(1[89]\d{2})\b', reference_string)
    year = year_match.group(1) if year_match else None
    
    author_hint = None
    if "," in reference_string:
        # Get everything before the first comma
        before_first_comma = reference_string.split(",", 1)[0].strip()
        # Find all valid alphanumeric words in that prefix segment
        words = re.findall(r'\b\w{3,}\b', before_first_comma)
        if words:
            # Grab the LAST word closest to the comma (the surname)
            author_hint = words[-1].lower()
    else:
        # Fallback if no comma exists
        author_match = re.search(r'\b([A-Za-z]{3,})\b', reference_string)
        author_hint = author_match.group(1).lower() if author_match else None
    
    return year, author_hint

def tokenize_string(s):
    """Splits a string into a set of lower-case alphanumeric words for instant lookup."""
    if s is None:
        return set()
    return set(re.findall(r'\b\w{3,}\b', str(s).lower()))

def load_and_index_jstor_stream(filepath):
    """
    Streams the real JSTOR JSONL file line-by-line.
    Optimized structure: index[year][author_word] = [articles...]
    """
    print(f"[*] Streaming and indexing {filepath}...")
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

            date_val = article.get("published_date")
            if date_val:
                date_str = str(date_val).strip()
                year_match = re.search(r'\b(1[89]\d{2})\b', date_str) or re.match(r'^(1[89]\d{2})', date_str)
                
                if year_match:
                    clean_year = year_match.group(1)
                    
                    if clean_year not in index:
                        index[clean_year] = {}
                    
                    title = article.get("title") or ""
                    title_tokens = tokenize_string(title)
                    
                    creators_str = article.get("creators_string")
                    creator_words = []
                    if creators_str is not None:
                        creator_words = re.findall(r'\b\w{3,}\b', str(creators_str).lower())
                    
                    record = {
                        "id": article.get("item_id"),
                        "title": title,
                        "title_tokens": title_tokens,
                        "creators_string": creators_str if creators_str else ""
                    }
                    
                    if creator_words:
                        for word in creator_words:
                            if word not in index[clean_year]:
                                index[clean_year][word] = []
                            index[clean_year][word].append(record)
                    else:
                        if "_UNKNOWN_AUTHOR_" not in index[clean_year]:
                            index[clean_year]["_UNKNOWN_AUTHOR_"] = []
                        index[clean_year]["_UNKNOWN_AUTHOR_"].append(record)
                        
                    count += 1
            
            if line_num % 500000 == 0:
                print(f"    -> Read {line_num} lines... Indexed {count} valid articles.")

    print(f"[✓] Successfully indexed {count} JSTOR articles across {len(index)} years.")
    return index

def main():
    # 1. Build or Load index using Pickle cache
    if os.path.exists(CACHE_FILE):
        print(f"[✓] Found cached index at {CACHE_FILE}. Loading instantly...")
        try:
            with open(CACHE_FILE, 'rb') as f:
                jstor_index = pickle.load(f)
            print("[✓] Successfully loaded index from cache.")
        except Exception as e:
            print(f"[!] Error loading cache: {e}. Falling back to file stream...")
            jstor_index = None
    else:
        jstor_index = None

    if not jstor_index:
        try:
            jstor_index = load_and_index_jstor_stream(JSTOR_METADATA_FILE)
            print(f"[*] Caching index to {CACHE_FILE} for future lightning runs...")
            with open(CACHE_FILE, 'wb') as f:
                pickle.dump(jstor_index, f, protocol=pickle.HIGHEST_PROTOCOL)
            print("[✓] Cache saved successfully.")
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

    # 3. Fast-match fields using highly-targeted dictionary routing
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
            
            # TWEAK: If the parsed author hint is null or empty, bypass matching entirely
            if not author_hint:
                ref_obj["id"] = "UNRESOLVED_EXTERNAL_OR_BOOK"
                unresolved_count += 1
                continue

            ref_tokens = tokenize_string(raw_ref)
            matched_candidates = []
            
            if year and year in jstor_index:
                year_bucket = jstor_index[year]
                
                # Directly grab records tied to this specific author token
                if author_hint in year_bucket:
                    target_candidates = year_bucket[author_hint]
                    
                    for candidate in target_candidates:
                        overlap = len(ref_tokens.intersection(candidate["title_tokens"]))
                        
                        if overlap >= 2:
                            matched_candidates.append({
                                "id": candidate["id"],
                                "title": candidate["title"],
                                "authors": candidate["creators_string"],
                                "overlap": overlap
                            })

            if matched_candidates:
                ref_obj["id"] = matched_candidates
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
    print(f"    - Matches Resolved (Lists inserted): {resolved_count}")
    print(f"    - Internal Abbreviations Skipped: {skipped_count}")
    print(f"    - Unresolved/Books: {unresolved_count}")

if __name__ == "__main__":
    main()