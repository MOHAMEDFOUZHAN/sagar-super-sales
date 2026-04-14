import os
import csv
from docx import Document

def convert_folder_docx_to_csv(source_folder, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    files = [f for f in os.listdir(source_folder) if f.endswith('.docx') and not f.startswith('~$')]
    
    print(f"Found {len(files)} Word documents.")

    for filename in files:
        docx_path = os.path.join(source_folder, filename)
        csv_filename = os.path.splitext(filename)[0] + '.csv'
        csv_path = os.path.join(output_folder, csv_filename)
        
        print(f"Processing {filename}...")
        
        try:
            doc = Document(docx_path)
            all_rows = []
            
            # Iterate through all tables in the document
            for table in doc.tables:
                for row in table.rows:
                    # Extract text from each cell, clean whitespace
                    row_data = [cell.text.strip().replace('\n', ' ') for cell in row.cells]
                    # Filter out completely empty rows
                    if any(row_data):
                        all_rows.append(row_data)
            
            if all_rows:
                with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerows(all_rows)
                print(f"  -> Saved to {csv_filename}")
            else:
                print(f"  -> Check: No table data found in {filename}")
                
        except Exception as e:
            print(f"  -> Error processing {filename}: {str(e)}")

if __name__ == "__main__":
    # Adjust paths as needed
    SOURCE_DIR = r"d:\Sales\BIZZ"
    OUTPUT_DIR = r"d:\Sales\BIZZ_CSV"
    
    convert_folder_docx_to_csv(SOURCE_DIR, OUTPUT_DIR)
