# ============================================================
# old_scripts/id_lookup.py
# Look up work IDs from sorted JSTOR metadata for matching.
# ============================================================
import json
import os

# --- CONFIGURATION ---
SORTED_JSTOR_FILE = "/Users/matthewma/Downloads/jstor_metadata_sorted.jsonl"

def extract_id_from_line(line_str):
    """Safely parses item_id without fully loading complex JSON structures."""
    try:
        if '"item_id":"' in line_str:
            start = line_str.find('"item_id":"') + 11
            end = line_str.find('"', start)
            return line_str[start:end]
    except Exception:
        pass
    return ""

def binary_search_jsonl(filepath, target_id):
    """Performs a disk-based binary search on a sorted JSONL file."""
    target_id = target_id.strip()
    
    with open(filepath, 'rb') as f:
        low = 0
        high = os.path.getsize(filepath)
        
        while low < high:
            mid = (low + high) // 2
            f.seek(mid)
            
            # Since jumping to a random byte hits the middle of a line,
            # read until the next newline to get a clean, complete line string
            f.readline() 
            
            line_pos = f.tell()
            line_bytes = f.readline()
            
            # If we hit the absolute end of the file, pull back our boundary
            if not line_bytes:
                high = mid
                continue
                
            line_str = line_bytes.decode('utf-8', errors='ignore')
            current_id = extract_id_from_line(line_str)
            
            if not current_id:
                # If a line is corrupted, move step boundaries slightly
                low = mid + 1
                continue
                
            if current_id == target_id:
                return json.loads(line_str)
            elif current_id < target_id:
                low = line_pos + len(line_bytes)
            else:
                high = mid
                
    return None

def main():
    if not os.path.exists(SORTED_JSTOR_FILE):
        print(f"[!] Error: Sorted file not found at {SORTED_JSTOR_FILE}")
        print("    Please run the terminal 'sort' command provided in Step 1 first.")
        return

    print("\n==================================================")
    print("SORTED DISK-BASED ID VERIFIER")
    print("==================================================")

    while True:
        target_id = input("\nEnter item_id: ").strip()
        if target_id.lower() in ['exit', 'quit']:
            break
            
        if not target_id:
            continue
            
        record = binary_search_jsonl(SORTED_JSTOR_FILE, target_id)
        
        if record:
            print("\n[ MATCH FOUND ]")
            print(json.dumps(record, indent=4, ensure_ascii=False))
        else:
            print(f"\n[✗] No entry found for ID: '{target_id}'")

if __name__ == "__main__":
    main()