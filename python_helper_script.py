import gzip
import json

item_ids = []
# Replace with the exact filename you downloaded
input_file = "/Users/matthewma/Downloads/jstor_metadata_2026-05-05.jsonl.gz" 
output_file = "mind_journal_item_ids.txt"

print(f"Starting extraction from {input_file}...")

with gzip.open(input_file, "rt", encoding="utf-8") as f:
    for line_number, line in enumerate(f, start=1):
        # Progress tracker
        if line_number % 10000 == 0:
            print(f"\rProcessing line: {line_number}", end="", flush=True)
        
        try:
            data = json.loads(line)
            
            # FILTER LOGIC:
            # 1. Check if the parent publication is 'Mind'
            # 2. (Optional) Check if content_type is 'article'
            journal_title = data.get("is_part_of", "")
            content_type = data.get("content_type", "")

            if journal_title and journal_title.lower() == "mind":
                if content_type == "article":
                    item_ids.append(data["item_id"])
                    
        except json.JSONDecodeError:
            continue

print(f"\nFound {len(item_ids)} articles from the journal 'Mind'.")

# Save to UTF-8 plain text file as required by JSTOR
with open(output_file, "w", encoding="utf-8") as f:
    for item_id in item_ids:
        f.write(f"{item_id}\n")

print(f"Success! Item IDs saved to: {output_file}")