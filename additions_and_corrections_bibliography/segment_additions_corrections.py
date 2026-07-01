# ============================================================
# additions_and_corrections_bibliography/segment_additions_corrections.py
# Segment additions and corrections text into per-author
# bibliography blocks for later extraction.
# ============================================================
import re

def segment_bibliography(text):
    # Dictionaries to hold our segmented data
    segmented_db = {
        "additions": [],
        "minor_corrections": [],
        "major_corrections": []
    }
    
    # Split text into lines for processing
    lines = text.split('\n')
    current_author = ""
    current_item = ""
    current_category = None
    
    # Regex patterns
    # Matches author headers like "11. JOACHIM JUNGIUS." or "701. RICHARD DEDEKIND."
    author_pattern = re.compile(r'^\d+\.\s+[A-Z\s\.\(\)\-]+$')
    
    # Matches item starts like "1.1. Essai sur...", "1. For...", "* 1. Wissenschaftslehre..."
    item_pattern = re.compile(r'^(\*\s*)?((\d+)\.(\d+)?\.)|(\[?[A-Za-z]+\]?)')
    decimal_pattern = re.compile(r'^\d+\.\d+\.')
    integer_pattern = re.compile(r'^(\*\s*)?\d+\.')
    
    # Keywords that strongly indicate a minor instruction rather than a full citation
    minor_keywords = ['For', 'read', '[Add]', '[Delete', 'Delete the', 'Translation inaccurate']

    def save_current_item():
        if current_item and current_category and current_author:
            segmented_db[current_category].append({
                "author_context": current_author.strip(),
                "entry": current_item.strip()
            })

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
            
        # Check if line is an author heading
        if author_pattern.match(line_stripped) and not line_stripped.startswith("1."):
            current_author = line_stripped
            continue
            
        # Check if line starts a new work/item under an author
        # Looks for numbers like "1.", "1.1.", "* 1." at the start of the line
        match = re.match(r'^(\*\s*)?\d+\.', line_stripped)
        
        if match:
            # Save the previous item before starting a new one
            save_current_item()
            current_item = line_stripped
            
            prefix = match.group(0)
            
            # Rule 1: Additions have decimals (e.g., 1.1.)
            if '.' in prefix.replace('*', '').strip() and prefix.count('.') > 1:
                current_category = "additions"
            
            # Rule 2 & 3: Integer numbers are corrections
            else:
                # Check if it contains instructional keywords indicating a minor correction
                is_minor = any(keyword.lower() in line_stripped.lower() for keyword in minor_keywords)
                
                if is_minor:
                    current_category = "minor_corrections"
                else:
                    # If it's an integer but lacks minor keywords, it's a full citation rewrite
                    current_category = "major_corrections"
        else:
            # If it doesn't start with a number, it's a continuation of the previous item
            if current_item:
                current_item += " " + line_stripped

    # Save the very last item
    save_current_item()
    
    return segmented_db

# Example usage (assuming your text is loaded into a variable called `biblio_text`):
db = segment_bibliography(biblio_text)
print(f"Found {len(db['additions'])} Additions.")
print(f"Found {len(db['minor_corrections'])} Minor Corrections.")
print(f"Found {len(db['major_corrections'])} Major Corrections.")