import re
import pdfplumber

def extract_authors_from_url(file_path_or_url):
    """
    Extracts author names (formatted as ALL CAPS.) from a PDF file.
    """
    authors = set()
    
    # In a real-world scenario, you might use: 
    # response = requests.get(file_path_or_url)
    # with open('temp.pdf', 'wb') as f: f.write(response.content)
    # and then open 'temp.pdf'.
    
    with pdfplumber.open(file_path_or_url) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                # Regex to find lines starting with ALL CAPS followed by a period.
                # This pattern matches common bibliographic headers in the doc.
                found = re.findall(r'^([A-Z\s]{3,}\.)', text, re.MULTILINE)
                for name in found:
                    authors.add(name.strip())
                    
    return list(authors)

# Example usage (assuming local file access)
author_list = extract_authors_from_url('/Users/matthewma/Downloads/church1984-addendum.pdf')
for author in author_list:
    print(author)