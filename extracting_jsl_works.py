import json
import time

def merge_join_nodes(sorted_ft_file, sorted_meta_file, output_file):
    start_time = time.time()
    processed_count = 0
    skipped_ft_none = 0
    skipped_meta_none = 0
    
    print("Beginning stream merge-join...")
    
    with open(sorted_ft_file, 'r', encoding='utf-8') as ft_f, \
         open(sorted_meta_file, 'r', encoding='utf-8') as meta_f, \
         open(output_file, 'w', encoding='utf-8') as out_f:
        
        ft_line = ft_f.readline()
        meta_line = meta_f.readline()
        
        while ft_line and meta_line:
            try:
                ft_data = json.loads(ft_line)
                meta_data = json.loads(meta_line)
            except json.JSONDecodeError:
                ft_line = ft_f.readline()
                meta_line = meta_f.readline()
                continue
            
            ft_id = ft_data.get('iid')
            meta_id = meta_data.get('item_id')
            
            # --- DEFENSIVE GUARD: Handle missing/None IDs safely ---
            if ft_id is None:
                skipped_ft_none += 1
                ft_line = ft_f.readline()
                continue
            
            if meta_id is None:
                skipped_meta_none += 1
                meta_line = meta_f.readline()
                continue
            # -------------------------------------------------------
            
            # Case 1: Perfect Match! Extract metadata and transcribe
            if ft_id == meta_id:
                node = {
                    "item_id": ft_id,
                    "title": meta_data.get("title"),
                    "creators": meta_data.get("creators"),
                    "is_part_of": meta_data.get("is_part_of"),
                    "publishers": meta_data.get("publishers"),
                    "published_date": meta_data.get("published_date"),
                    "url": meta_data.get("url"),
                    "raw_references": ft_data.get("references", [])
                }
                out_f.write(json.dumps(node) + '\n')
                processed_count += 1
                
                if processed_count % 10000 == 0:
                    print(f"  Successfully matched {processed_count} JSL nodes...")
                
                # Advance both streams
                ft_line = ft_f.readline()
                meta_line = meta_f.readline()
                
            # Case 2: Full-text ID string is sorted further ahead alphabetically; advance metadata stream
            elif ft_id > meta_id:
                meta_line = meta_f.readline()
                
            # Case 3: Metadata ID string is sorted further ahead alphabetically; advance full-text stream
            else:
                ft_line = ft_f.readline()

    print(f"\nCompleted in {time.time() - start_time:.2f} seconds!")
    print(f"Total JSL nodes written to {output_file}: {processed_count}")
    if skipped_ft_none or skipped_meta_none:
        print(f"Safely skipped bad rows: {skipped_ft_none} from full-text, {skipped_meta_none} from metadata.")

# Run the lightning-fast merge join
merge_join_nodes("/Users/matthewma/Downloads/jsl_full_text_sorted.jsonl", "/Users/matthewma/Downloads/jstor_metadata_sorted.jsonl", "jsl_works.jsonl")