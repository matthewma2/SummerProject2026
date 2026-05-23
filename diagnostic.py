import re
import json
import time
import pdfplumber

def load_target_names(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

def extract_text_from_pdf(pdf_path):
    print(f"--- DIAGNOSTIC CHECK FOR: {pdf_path} ---")
    full_text_list = []
    
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total pages identified in file: {len(pdf.pages)}")
        
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text:
                full_text_list.append(text)
            else:
                # If this prints for page 1, 2, 3... it means it's a scanned image PDF!
                print(f"  [ALERT] Page {page_num}: Extract text returned EMPTY. No text layer detected.")
                
    combined_text = " ".join(full_text_list)
    
    # --- VISUAL DEBUG WINDOW ---
    print("\n--- FIRST 500 CHARACTERS EXTRACTED FROM PDF LAYER ---")
    if not combined_text.strip():
        print("[CRITICAL] The extracted text stream is COMPLETELY BLANK. This PDF requires OCR.")
    else:
        print(combined_text[:500] + "\n...")
    print("-----------------------------------------------------\n")
    
    return combined_text

def extract_citations_from_text(text, name_list, window=50):
    extracted_citations = []
    
    # Quick sanity check: lowercase the text block for a manual fallback scan
    text_lower = text.lower()
    if "kant" in text_lower:
        print("[DEBUG] Confirmed: The raw string 'kant' DOES exist physically in the text layer!")
    else:
        print("[DEBUG] Alert: The raw string 'kant' does NOT exist anywhere in the extracted text stream.")

    for name in name_list:
        pattern = rf'\b{re.escape(name)}\b'
        
        for match in re.finditer(pattern, text, re.IGNORECASE):
            start = max(0, match.start() - window)
            end = min(len(text), match.end() + window)
            snippet = text[start:end].replace('\n', ' ').strip()
            
            year_match = re.search(r'\b(1[5-9]\d{2}|20[0-2]\d)\b', snippet)
            
            if year_match:
                found_year = year_match.group(1)
                extracted_citations.append({
                    "extracted_author": name,
                    "extracted_year": found_year,
                    "context_window": f"...{snippet}..."
                })
                
    return extracted_citations

def run_pipeline(pdf_file_path, names_file_path, output_json_path):
    target_names = load_target_names(names_file_path)
    raw_article_text = extract_text_from_pdf(pdf_file_path)
    
    results = extract_citations_from_text(raw_article_text, target_names)
    
    with open(output_json_path, 'w', encoding='utf-8') as out_f:
        json.dump(results, out_f, indent=4, ensure_ascii=False)
        
    print(f"Total citations extracted matching criteria: {len(results)}")

# --- RUN DIAGNOSTIC ---
# Make sure this points to your actual file name
sample_mind_pdf = "/Users/matthewma/Downloads/Sidgwick-Mind-1880.pdf" 

run_pipeline(
    pdf_file_path=sample_mind_pdf,
    names_file_path="target_surnames.txt",
    output_json_path="extracted_mind_citations.json"
)