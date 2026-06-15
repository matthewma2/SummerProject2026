import json
import os
import time
import requests

def query_crossref_for_citations(input_txt, output_json):
    if not os.path.exists(input_txt):
        print(f"Error: '{input_txt}' not found.")
        return

    # Load unique lines from your text file
    with open(input_txt, "r", encoding="utf-8") as f:
        raw_citations = [line.strip() for line in f if line.strip()]

    print(f"Loaded {len(raw_citations)} citations to query.")

    # Shared mapping dictionary (loads existing progress if script was stopped)
    resolved_map = {}
    if os.path.exists(output_json):
        with open(output_json, "r", encoding="utf-8") as f:
            resolved_map = json.load(f)
        print(f"Found existing progress. {len(resolved_map)} items already resolved.")

    crossref_url = "https://api.crossref.org/works"
    
    # Polite Pool Etiquette: Add your email to speed up requests and avoid blocks
    headers = {
        "User-Agent": "CitationGraphProject/1.0 (mailto:monsteryolo123@gmail.com)"
    }

    count = 0
    success_count = 0

    try:
        for citation in raw_citations:
            # Skip if already processed in a previous run
            if citation in resolved_map:
                continue

            count += 1
            if count % 10 == 0:
                print(f"Processing item {count}/{len(raw_citations)}...")

            try:
                # query.bibliographic runs an unstructured text query through Crossref's parser
                params = {"query.bibliographic": citation, "rows": 1}
                response = requests.get(crossref_url, headers=headers, params=params, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    items = data.get("message", {}).get("items", [])

                    if items:
                        top_match = items[0]
                        score = top_match.get("score", 0)

                        # A matching score > 60 usually indicates a reliable text match
                        if score >= 60:
                            doi = top_match.get("DOI")
                            resolved_map[citation] = f"doi:{doi}"
                            success_count += 1
                        else:
                            # If match confidence is too low, mark it as null to investigate later
                            resolved_map[citation] = None
                    else:
                        resolved_map[citation] = None
                else:
                    print(f"API Error (Status {response.status_code}) on string: {citation[:30]}...")
                
                # Respectful rate-limiting delay (5 requests per second)
                time.sleep(0.2)

            except Exception as e:
                print(f"Network or parsing error on item: {e}")
                continue

            # Periodically checkpoint results so you don't lose data if interrupted
            if count % 50 == 0:
                with open(output_json, "w", encoding="utf-8") as f:
                    json.dump(resolved_map, f, indent=4, ensure_ascii=False)

    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Saving current progress...")

    # Final save
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(resolved_map, f, indent=4, ensure_ascii=False)

    print("\n--- Processing Complete ---")
    print(f"Total new queries run: {count}")
    print(f"Successfully matched to DOIs: {success_count}")
    print(f"Mapping dictionary saved to '{output_json}'")

if __name__ == "__main__":
    query_crossref_for_citations("unresolved_external_references.txt", "resolved_mapping.json")