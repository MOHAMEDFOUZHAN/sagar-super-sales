import pypdf
import sys

def extract_text(pdf_path):
    try:
        reader = pypdf.PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    path = r"d:\Sales\SAGAR REPORTS.pdf"
    print(f"Reading {path}...")
    try:
        reader = pypdf.PdfReader(path)
        print(f"Number of pages: {len(reader.pages)}")
        text = ""
        for i, page in enumerate(reader.pages):
            print(f"Extracting page {i+1}...")
            text += page.extract_text() + "\n"
        print("Extraction complete.")
        with open("extracted_report.txt", "w", encoding="utf-8") as f:
            f.write(text)
        print("Content saved to extracted_report.txt")
    except Exception as e:
        print(f"Error: {e}")
