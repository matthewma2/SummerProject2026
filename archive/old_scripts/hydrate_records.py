# ============================================================
# hydrate_records.py
# Hydrate citation and work records with additional metadata
# from external sources and stored data files.
# ============================================================
import json
import os
import time
import requests

def hydrate_dois(mapping_json, output_metadata_json):
    if not os.path.exists(mapping_json):
        print(f"Error: '{mapping_json}' not found.")
        return

    # Load your mapping file
    with open(mapping_json, "r", encoding="utf-8") as f:
        mapping_data = json.load(f)

    # Filter out nulls to get only the valid DOIs
    doi_to_resolve = {raw_str: doi for raw_str, doi in mapping_data.items() if doi is not None}
    print(f"Loaded {len(doi_to_resolve)} unique DOIs to hydrate.")

    # Load existing metadata cache if you need to resume later
    metadata_catalog = {}
    if os.path.exists(output_metadata_json):
        with open(output_metadata_json, "r", encoding="utf-8") as f:
            metadata_catalog = json.load(f)

    # Standard headers for DOI content negotiation
    # We ask for a structured citeproc-json format, which is standard across publishers
    headers = {
        "Accept": "application/vnd.citationstyles.csl+json",
        "User-Agent": "CitationGraphProject/1.0 (mailto:your.email@example.com)"
    }

    count = 0
    for raw_str, doi_uri in doi_to_resolve.items():
        # Clean the key (remove 'doi:' prefix if your script added it, to get the raw string)
        raw_doi = doi_uri.replace("doi:", "") if doi_uri.startswith("doi:") else doi_uri
        
        if raw_doi in metadata_catalog:
            continue  # Already fetched

        count += 1
        if count % 20 == 0:
            print(f"Fetched metadata for {count} records...")

        url = f"https://doi.org/{raw_doi}"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                meta = response.json()
                
                # Extract clean, structural parameters for your database layout
                metadata_catalog[raw_doi] = {
                    "doi": raw_doi,
                    "title": meta.get("title", "Unknown Title"),
                    "authors": [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in meta.get("author", [])],
                    "container_title": meta.get("container-title", "Unknown Venue"),
                    "volume": meta.get("volume"),
                    "issue": meta.get("issue"),
                    "page": meta.get("page"),
                    "year": meta.get("issued", {}).get("date-parts", [[None]])[0][0]
                }
            else:
                print(f"Failed to fetch metadata for DOI: {raw_doi} (Status {response.status_code})")
            
            # Brief pause to respect server limits
            time.sleep(0.1)

        except Exception as e:
            print(f"Network error on DOI {raw_doi}: {e}")
            continue

        # Checkpoint progress
        if count % 50 == 0:
            with open(output_metadata_json, "w", encoding="utf-8") as f:
                json.dump(metadata_catalog, f, indent=4, ensure_ascii=False)

    # Save final output
    with open(output_metadata_json, "w", encoding="utf-8") as f:
        json.dump(metadata_catalog, f, indent=4, ensure_ascii=False)

    print(f"\nHydration complete! Structured metadata catalog saved to '{output_metadata_json}'")

if __name__ == "__main__":
    hydrate_dois("resolved_mapping.json", "external_works_metadata.json")