# ============================================================
# old_scripts/title_lookup.py
# Look up and align work titles against the bibliography index.
# ============================================================
import json
import os

# --- CONFIGURATION ---
# CRITICAL: This file MUST be pre-sorted alphabetically by the "title" field!
SORTED_JSTOR_TITLE_FILE = "/Users/matthewma/Downloads/jstor_metadata_sorted_by_title.jsonl"

def extract_title_from_line(line_str):
    """Safely extracts the title value without fully parsing complex JSON structures."""
    try:
        if '"title":"' in line_str:
            start = line_str.find('"title":"') + 9
            end = line_str.find('"', start)
            return line_str[start:end]
    except Exception:
        pass
    return ""

def binary_search_jsonl_by_title(filepath, target_title):
    """Performs a disk-based binary search on a JSONL file sorted by title."""
    # Convert to lowercase if you want case-insensitive matching, 
    # but your file sorting must match this logic.
    target_title = target_title.strip()
    
    with open(filepath, 'rb') as f:
        low = 0
        high = os.path.getsize(filepath)
        
        while low < high:
            mid = (low + high) // 2
            f.seek(mid)
            
            # Jump to the start of the next clean line
            f.readline() 
            
            line_pos = f.tell()
            line_bytes = f.readline()
            
            # If we hit the absolute end of the file, pull back our boundary
            if not line_bytes:
                high = mid
                continue
                
            line_str = line_bytes.decode('utf-8', errors='ignore')
            current_title = extract_title_from_line(line_str)
            
            if not current_title:
                # If a line is corrupted or has no title, skip past it
                low = mid + 1
                continue
                
            if current_title == target_title:
                return json.loads(line_str)
            elif current_title < target_title:
                low = line_pos + len(line_bytes)
            else:
                high = mid
                
    return None

def main():
    if not os.path.exists(SORTED_JSTOR_TITLE_FILE):
        print(f"[!] Error: Sorted file not found at {SORTED_JSTOR_TITLE_FILE}")
        print("    Please ensure your JSONL file is sorted by title before running.")
        return

    print("\n==================================================")
    print("SORTED DISK-BASED TITLE VERIFIER")
    print("==================================================")

    while True:
        target_title = input("\nEnter exact title: ").strip()
        if target_title.lower() in ['exit', 'quit']:
            break
            
        if not target_title:
            continue
            
        print(f"Searching for: '{target_title}'...")
        record = binary_search_jsonl_by_title(SORTED_JSTOR_TITLE_FILE, target_title)
        
        if record:
            print("\n[ MATCH FOUND ]")
            print(json.dumps(record, indent=4, ensure_ascii=False))
        else:
            print(f"\n[✗] No entry found for Title: '{target_title}'")
            print("    Note: Match must be exact (case-sensitive, punctuation, etc.)")

if __name__ == "__main__":
    main()