# ============================================================
# extract_jsl_external_references.py
# Extract and normalize external references from JSL citation
# data for later matching and resolution.
# ============================================================
import json
import os
import re

def is_internal_contextual(text):
    """
    Returns True if the text matches internal citation patterns, false citation fragments,
    or bare bracket/page counts. Returns False for real, substantive citations.
    """
    text = text.strip()
    if not text:
        return True

    # 1. Matches standard or broken brackets/parentheses at the start:
    # '[4]', '[11]', '(3]', '10] p. 359', '11, p. 308]'
    if re.match(r'^\[?\d+[\]\)]', text) or re.match(r'^\d+[\],]', text):
        return True

    # 2. Matches bare numbers or numeric ranges with optional page annotations:
    # '11', '12', '16–17 (p. 218)', '10–13 (p. 222)', '22 (p. 233)'
    # (Uses \W to catch hyphens, en-dashes, spaces, and parentheses)
    if re.match(r'^\d+(\s*[\W\d]+\s*(p\.\s*\d+|page\s*\d+)?\)?\s*)?$', text):
        return True
        
    # 3. Double-check for standalone small integers that might have missed rule 2
    if text.isdigit() and len(text) <= 4:
        return True

    return False

def extract_clean_unresolved(input_json, output_txt):
    if not os.path.exists(input_json):
        print(f"Error: '{input_json}' not found.")
        return

    with open(input_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    unique_external_refs = set()
    total_refs = 0
    null_id_count = 0
    filtered_count = 0

    for item in data:
        for ref in item.get("references", []):
            total_refs += 1
            
            if ref.get("id") is None:
                null_id_count += 1
                text = ref.get("reference", "").strip()
                
                # Apply the robust contextual filter
                if is_internal_contextual(text):
                    filtered_count += 1
                    continue
                
                unique_external_refs.add(text)

    # Save out the high-confidence unique lines
    with open(output_txt, "w", encoding="utf-8") as out:
        for ref_str in sorted(unique_external_refs):
            out.write(f"{ref_str}\n")

    print("--- Refined Extraction Summary ---")
    print(f"Total references inspected: {total_refs}")
    print(f"References with id=null: {null_id_count}")
    print(f"Internal/Contextual items filtered: {filtered_count}")
    print(f"Clean unique external strings saved: {len(unique_external_refs)}")
    print(f"Output saved directly to: '{output_txt}'")

if __name__ == "__main__":
    extract_clean_unresolved("jsl_citations_resolved.json", "unresolved_external_references.txt")