import json
import sqlite3
import os

def generate_nodes_with_sqlite(full_text_file, metadata_file, output_file):
    db_path = "metadata_temp.db"
    
    # Connect to a local disk-based database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Turbo-charge settings
    cursor.execute("PRAGMA synchronous = OFF") # Don't wait for disk confirmation
    cursor.execute("PRAGMA journal_mode = MEMORY") # Keep temp logs in RAM
    cursor.execute("PRAGMA cache_size = 1000000") # Use 1GB of RAM for cache
    
    # 1. Create a table for the metadata
    cursor.execute('DROP TABLE IF EXISTS metadata')
    cursor.execute('''
        CREATE TABLE metadata (
            item_id TEXT PRIMARY KEY,
            content TEXT
        )
    ''')
    
    # 2. Stream metadata into the Database (Disk-based, not RAM)
    print("Streaming metadata to disk index...")
    with open(metadata_file, 'r', encoding='utf-8') as f:
        batch = []
        for count, line in enumerate(f):
            try:
                data = json.loads(line)
                # We store the whole JSON string to retrieve it later
                batch.append((data['item_id'], line.strip()))
                
                if len(batch) >= 10000:
                    cursor.executemany('INSERT OR IGNORE INTO metadata VALUES (?, ?)', batch)
                    conn.commit()
                    batch = []
                    print(f"  Indexed {count} entries...")
            except json.JSONDecodeError:
                continue
        # Insert remaining
        if batch:
            cursor.executemany('INSERT OR IGNORE INTO metadata VALUES (?, ?)', batch)
            conn.commit()

    # 3. Process Full-Text by querying the Database
    print("\nGenerating node list by joining files...")
    processed_count = 0
    with open(full_text_file, 'r', encoding='utf-8') as ft_in, \
         open(output_file, 'w', encoding='utf-8') as node_out:
        
        for line in ft_in:
            try:
                article = json.loads(line)
                article_id = article.get('item_id')
                
                # Query the disk-index for this specific ID
                cursor.execute('SELECT content FROM metadata WHERE item_id = ?', (article_id,))
                result = cursor.fetchone()
                
                if result:
                    meta = json.loads(result[0])
                    node = {
                        "item_id": article_id,
                        "title": meta.get("title"),
                        "creators": meta.get("creators"),
                        "is_part_of": meta.get("is_part_of"),
                        "publishers": meta.get("publishers"),
                        "published_date": meta.get("published_date"),
                        "url": meta.get("url"),
                        "raw_references": article.get("references", [])
                    }
                    node_out.write(json.dumps(node) + '\n')
                    processed_count += 1
                
                if processed_count % 1000 == 0:
                    print(f"  Created {processed_count} nodes...")
            except json.JSONDecodeError:
                continue

    conn.close()
    # Optional: Remove the temp database file when done
    # os.remove(db_path)
    print(f"\nSuccess! Node list created at: {output_file}")

# Usage
generate_nodes_with_sqlite("jsl_fulltext_dataset.jsonl", "/Users/matthewma/Downloads/jstor_metadata_2026-05-05.jsonl", "jsl_works.jsonl")


