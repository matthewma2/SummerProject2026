import json

# Define your file paths
input_filename = "filtered_jsl_works.jsonl"  # Replace with your actual input file name
output_filename = "jsl_citations.json"

transformed_data = []

# Open and read the original file line by line
with open(input_filename, "r", encoding="utf-8") as infile:
    for line in infile:
        # Skip empty lines if any exist
        if not line.strip():
            continue
            
        try:
            # Parse the individual JSON object from the line
            item = json.loads(line)
            
            # Extract the item_id and raw_references list
            item_id = item.get("item_id")
            raw_refs = item.get("raw_references", [])
            
            # Build the list of reference objects, defaulting id to None (null in JSON)
            references_list = [
                {"reference": ref, "id": None} 
                for ref in raw_refs
            ]
            
            # Construct the new object structure
            transformed_object = {
                "source": item_id,
                "references": references_list
            }
            
            # Append to our main list
            transformed_data.append(transformed_object)
            
        except json.JSONDecodeError as e:
            print(f"Skipping invalid JSON line: {e}")

# Save the final structured list as a standard JSON file
with open(output_filename, "w", encoding="utf-8") as outfile:
    json.dump(transformed_data, outfile, indent=4, ensure_ascii=False)

print(f"Successfully transformed {len(transformed_data)} items and saved to '{output_filename}'!")