import json
import re

# --- CONFIGURATION ---
WORKS_FILE = "works.json"
AUTHORS_FILE = "authors.json"
CITATIONS_FILE = "jsl_citations_resolved.json"
UPDATED_WORKS_FILE = "works_updated.json"
UPDATED_CITATIONS_FILE = "jsl_citations_final.json"

def load_author_matcher(authors_path):
    """Loads authors from authors.json and sorts them by name length descending."""
    with open(authors_path, 'r', encoding='utf-8') as f:
        authors_data = json.load(f)
    
    matcher_list = []
    for author in authors_data:
        author_id = author.get("id")
        names_to_check = []
        
        if author.get("full_name"):
            names_to_check.append(author["full_name"].strip())
        for alt in author.get("alternative_names", []):
            names_to_check.append(alt.strip())
            
        names_to_check = sorted(list({n for n in names_to_check if n}), key=len, reverse=True)
        for name in names_to_check:
            matcher_list.append({
                "name": name,
                "lower_name": name.lower(),
                "id": author_id
            })
            
    matcher_list.sort(key=lambda x: len(x["name"]), reverse=True)
    return matcher_list

def parse_reference_details(raw_ref, author_matcher):
    """Extracts year, real author IDs, an ID string hint, and cleans the title."""
    clean_ref = re.sub(r'^\[\d+\]\s*', '', raw_ref.strip())
    
    # 1. Extract Year
    year_match = re.search(r'\b(1[89]\d{2})\b', clean_ref)
    year = int(year_match.group(1)) if year_match else None
    
    # Isolate prefix segment for fallback author parsing
    if year_match:
        prefix_segment = clean_ref.split(year_match.group(1), 1)[0]
    elif "," in clean_ref:
        prefix_segment = clean_ref.split(",", 1)[0]
    else:
        prefix_segment = clean_ref

    # 2. Extract ONLY valid Author IDs from authors.json
    matched_author_ids = []
    matched_names = []
    
    ref_lower = clean_ref.lower()
    for item in author_matcher:
        if item["lower_name"] in ref_lower:
            if item["id"] not in matched_author_ids:
                matched_author_ids.append(item["id"])
                matched_names.append(item["name"])
    
    # Determine the text surname hint to use for the Work ID string
    if matched_names:
        primary_hint = matched_names[0].split()[-1].lower()
    else:
        # Fallback text parsing to get a surname for the ID string, without creating a fake author ID
        words = re.findall(r'\b[a-zA-Z]{3,}\b', prefix_segment.lower())
        ignored = {'and', 'von', 'van', 'der', 'the', 'vol', 'journal'}
        hints = [w for w in words if w not in ignored]
        primary_hint = hints[0] if hints else "unknown"

    # 3. Extract Title Heuristic
    title = None
    quote_match = re.search(r'["\"\'“”‘’«»]([^"\"\'“”‘’«»]{5,})["\"\'“”‘’«»]', clean_ref)
    if quote_match:
        title = quote_match.group(1).strip()
        
    if not title:
        segments = [s.strip() for s in clean_ref.split(',')]
        valid_segments = []
        for seg in segments:
            seg_lower = seg.lower()
            if any(m in seg_lower for m in ['vol.', 'pp.', 'p.', 'no.', 'part', 'press', 'amsterdam', 'princeton']):
                break
            if re.search(r'\b1[89]\d{2}\b', seg) and len(seg) < 10:
                break
            valid_segments.append(seg)
            
        title_candidates = []
        for seg in valid_segments:
            seg_lower = seg.lower()
            if any(name.lower() in seg_lower for name in matched_names) and len(seg) < 25:
                continue
            if re.match(r'^[A-Z\.\s]+$', seg) and len(seg) < 8:
                continue
            title_candidates.append(seg)
            
        if title_candidates:
            title = title_candidates[0]
            
    if not title or len(title) < 3:
        title = clean_ref.split(',')[0] if ',' in clean_ref else clean_ref
        
    title = re.sub(r'[\.,\s"\'\’]+$', '', title).strip()
    return year, matched_author_ids, primary_hint, title

def get_alpha_suffix(index):
    """Converts 0->a, 25->z, 26->aa..."""
    result = ""
    while index >= 0:
        result = chr(97 + (index % 26)) + result
        index = (index // 26) - 1
    return result

def generate_unique_id(author_hint, year, existing_ids):
    """Generates a hyphenless ID standard: SurnameYearSuffix (e.g., Quine1938a)."""
    safe_author = author_hint.capitalize()
    safe_year = str(year) if year else "ND"
    
    # Completely strip non-alphanumeric characters to keep it perfectly clean
    base_id = re.sub(r'[^a-zA-Z0-9]', '', f"{safe_author}{safe_year}")
    
    counter = 0
    while True:
        candidate_id = f"{base_id}{get_alpha_suffix(counter)}"
        if candidate_id not in existing_ids:
            return candidate_id
        counter += 1

def main():
    print("[*] Loading author lookup rules...")
    author_matcher = load_author_matcher(AUTHORS_FILE)
    
    print(f"[*] Loading master databases...")
    with open(WORKS_FILE, 'r', encoding='utf-8') as f:
        works_data = json.load(f)
        
    with open(CITATIONS_FILE, 'r', encoding='utf-8') as f:
        citations_data = json.load(f)

    existing_ids = {work["id"] for work in works_data if "id" in work}
    raw_ref_to_id = {}
    new_works_count = 0
    skipped_count = 0

    print("[*] Processing unresolved elements...")
    for entry in citations_data:
        for ref_obj in entry.get("references", []):
            if ref_obj.get("id") is not None:
                continue
                
            raw_ref = ref_obj.get("reference", "").strip()
            if re.match(r'^\[\d+\]\s*(.*)$', raw_ref) and len(raw_ref) < 15:
                skipped_count += 1
                continue
                
            if raw_ref in raw_ref_to_id:
                ref_obj["id"] = raw_ref_to_id[raw_ref]
                continue
                
            year, author_ids, author_hint, extracted_title = parse_reference_details(raw_ref, author_matcher)
            new_id = generate_unique_id(author_hint, year, existing_ids)
            
            ref_obj["id"] = new_id
            raw_ref_to_id[raw_ref] = new_id
            existing_ids.add(new_id)
            
            new_work = {
                "id": new_id,
                "title": extracted_title if extracted_title else "Unknown Title",
                "authors": author_ids,  # Contains only authentic IDs from authors.json or remains empty []
                "year": year,
                "type": "book" if "book" in raw_ref.lower() or "press" in raw_ref.lower() else "article",
                "raw_reference": raw_ref
            }
            works_data.append(new_work)
            new_works_count += 1

    print(f"[*] Saving files...")
    with open(UPDATED_WORKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(works_data, f, indent=4, ensure_ascii=False)
        
    with open(UPDATED_CITATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(citations_data, f, indent=4, ensure_ascii=False)

    print(f"\n[✓] Done! Added {new_works_count} new entries with true schema tracking.")

if __name__ == "__main__":
    main()