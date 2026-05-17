import json

# Extracting articles published from 1936 to 1970 in The Journal of Symbolic Logic
input_file = '/Users/matthewma/Downloads/jstor_metadata_2026-05-05.jsonl' 
output_file = 'jsl_item_id_list.txt'

jsl_ids = []
line_count = 0

print("Starting extraction... (Press Ctrl+C to stop, but it may take a while)")

with open(input_file, 'r', encoding='utf-8') as f:
    for line in f:
        line_count += 1
        
        # Print progress every 100,000 lines so you know it's working
        if line_count % 100000 == 0:
            print(f"\rProcessing line: {line_count}", end="", flush=True)

        try:
            data = json.loads(line)
            
            # Check identifiers first (usually faster than date parsing)
            identifiers = data.get('identifiers', {})
            if identifiers and identifiers.get('journal_code') == "jsymboliclogic":
                
                # Only parse the date if the journal code matches
                date_str = data.get('published_date')
                if date_str and len(date_str) >= 4:
                    try:
                        year = int(date_str[:4])
                        if 1936 <= year <= 1970:
                            item_id = data.get('item_id')
                            if item_id:
                                jsl_ids.append(item_id)
                    except ValueError:
                        continue
                        
        except json.JSONDecodeError:
            continue

# Final save
with open(output_file, 'w') as out:
    for item_id in jsl_ids:
        out.write(f"{item_id}\n")

print(f"\nFinished! Total lines scanned: {line_count}")
print(f"Total JSL articles found: {len(jsl_ids)}")