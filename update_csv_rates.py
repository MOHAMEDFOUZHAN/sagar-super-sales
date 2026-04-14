import csv
import os

def update_csv_rates():
    base_dir = r"d:\Sales\BIZZ_CSV"
    
    # 1. SPICES.csv Updates
    spices_file = os.path.join(base_dir, "SPICES.csv")
    spices_updates = {
        "CLOVES (A) 100G": 230,
        "CLOVES (A) 50G": 115,
        "CLOVES (A) 250G": 575,
        "DRY GINGER-100G": 70,
        "DRY GINGER-250G": 175,
        "MACE (A) 50G": 280,
        "MACE (A) 100G": 560
    }
    
    update_file(spices_file, spices_updates)

    # 2. OILS.csv Updates
    oils_file = os.path.join(base_dir, "OILS.csv")
    oils_updates = {
        "L.G-OIL – 60": 190,
        "L.G-OIL – 100": 310,
        "L.G-OIL – 200": 620,
        "L.G-OIL – 500": 1550,
        "CITRIDORA-OIL – 100": 310,
        "CITRIDORA-OIL – 200": 620,
        "CITRIDORA-OIL – 500": 1550
    }
    # Note: Using CITRIDORA-OIL as match for "Citronella" based on price analysis
    
    update_file(oils_file, oils_updates)
    print("All CSVs updated.")

def update_file(filepath, updates):
    print(f"Updating {os.path.basename(filepath)}...")
    rows = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        rows.append(header)
        
        for row in reader:
            new_row = list(row)
            # Check Column 1 (Left Side)
            if len(new_row) > 1:
                item_name = new_row[1].strip()
                if item_name in updates:
                    print(f"  - Updating {item_name}: {new_row[2]} -> {updates[item_name]}")
                    new_row[2] = str(updates[item_name])
            
            # Check Column 5 (Right Side)
            if len(new_row) > 5:
                item_name = new_row[5].strip()
                if item_name in updates:
                    print(f"  - Updating {item_name}: {new_row[6]} -> {updates[item_name]}")
                    new_row[6] = str(updates[item_name])
            
            rows.append(new_row)
            
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(rows)

if __name__ == "__main__":
    update_csv_rates()
