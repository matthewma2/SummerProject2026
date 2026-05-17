import json
import time

def should_filter_out(article):
    """
    Returns True if the article has an invalid title OR a missing/null creators field.
    """
    title_string = article.get("title", "")
    creators = article.get("creators")
    
    # 1. Check Title Criteria
    if not title_string or title_string.strip() == "":
        return True
        
    """
    clean_title = title_string.lower().strip()
    exclusions = ["front matter", "back matter", "errata", "corrigenda"]
    for phrase in exclusions:
        if phrase in clean_title:
            return True
    """
            
    # 2. Check Creators Criteria (filters out null, None, or empty lists [])
    if creators is None or creators == []:
        return True
        
    return False

def filter_jsonl_file(input_file_path, output_file_path):
    start_time = time.time()
    processed_count = 0
    filtered_count = 0
    
    print(f"Filtering {input_file_path} based on Title and Creators criteria...")
    
    with open(input_file_path, 'r', encoding='utf-8') as infile, \
         open(output_file_path, 'w', encoding='utf-8') as outfile:
        
        for line in infile:
            try:
                article = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            # Apply the OR filtering criteria
            if should_filter_out(article):
                filtered_count += 1
                continue
            
            # Extract clean node format if it passes both checks
            node = {
                "item_id": article.get("item_id"),
                "title": article.get("title"),
                "creators": article.get("creators"),
                "published_date": article.get("published_date"),
                "url": article.get("url"),
                "raw_references": article.get("raw_references", [])
            }
            
            outfile.write(json.dumps(node) + '\n')
            processed_count += 1
            
            if processed_count % 10000 == 0:
                print(f"  Written {processed_count} valid nodes...")

    print(f"\n--- Done! ---")
    print(f"Valid nodes kept (Has title AND creators): {processed_count}")
    print(f"Nodes removed (Missing title OR creators): {filtered_count}")
    print(f"Total execution time: {time.time() - start_time:.2f} seconds")

# --- Execute Script ---
filter_jsonl_file(
    "jsl_works.jsonl", 
    "filtered_jsl_works.jsonl"
)