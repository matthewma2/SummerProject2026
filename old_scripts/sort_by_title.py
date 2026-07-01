# ============================================================
# old_scripts/sort_by_title.py
# Sort JSTOR metadata records alphabetically by title.
# ============================================================
import json
import os

INPUT_FILE = "/Users/matthewma/Downloads/jstor_metadata.jsonl"
OUTPUT_FILE = "/Users/matthewma/Downloads/jstor_metadata_sorted_by_title.jsonl"

def sort_jsonl_by_title():
    print("Step 1: Scanning file and indexing titles...")
    offsets = []
    
    with open(INPUT_FILE, 'rb') as f:
        while True:
            offset = f.tell()
            line = f.readline()
            if not line:
                break
                
            try:
                # We decode and peek at the title
                line_str = line.decode('utf-8', errors='ignore')
                if '"title":"' in line_str:
                    start = line_str.find('"title":"') + 9
                    end = line_str.find('"', start)
                    title = line_str[start:end]
                else:
                    title = ""
                
                offsets.append((title, offset, len(line)))
            except Exception:
                continue

    print("Step 2: Sorting index by title alphabetically...")
    # This sorts purely based on the title string
    offsets.sort(key=lambda x: x[0])

    print("Step 3: Writing sorted file to disk...")
    with open(INPUT_FILE, 'rb') as infile, open(OUTPUT_FILE, 'wb') as outfile:
        for _, offset, length in offsets:
            infile.seek(offset)
            outfile.write(infile.read(length))

    print(f"\n[SUCCESS] Saved title-sorted file to:\n{OUTPUT_FILE}")

if __name__ == "__main__":
    sort_jsonl_by_title()