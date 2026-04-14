import os
import csv
import mysql.connector
from config import Config

def get_db_connection():
    return mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB
    )

def clean_money(val):
    if not val:
        return 0.0
    val = str(val).replace(',', '').strip()
    try:
        return float(val)
    except:
        return 0.0

def import_csv_to_db(folder_path):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]
    
    total_added = 0
    
    for filename in files:
        category = os.path.splitext(filename)[0].upper() # Use filename as category
        file_path = os.path.join(folder_path, filename)
        print(f"Importing {category}...")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None) # Skip header
            
            for row in reader:
                # The CSV has double columns (side by side), so we process two items per row
                # Set 1: Col 0-3
                if len(row) >= 4:
                    process_item(cursor, row[0], row[1], row[2], row[3], category)
                
                # Set 2: Col 4-7
                if len(row) >= 8:
                    process_item(cursor, row[4], row[5], row[6], row[7], category)
                    
    conn.commit()
    conn.close()
    print(" Import Complete!")

def process_item(cursor, code, name, rate, bizz, category):
    if not code or not name:
        return

    # Clean data
    code = "1" + str(code.strip()) # Add '1' prefix as requested
    name = name.strip()
    rate = clean_money(rate)
    bizz = clean_money(bizz)
    
    # Insert or Update
    cursor.execute("""
        INSERT INTO products (barcode, name, category, price, bizz, current_stock)
        VALUES (%s, %s, %s, %s, %s, 100)
        ON DUPLICATE KEY UPDATE
        name = VALUES(name),
        price = VALUES(price),
        bizz = VALUES(bizz),
        category = VALUES(category)
    """, (code, name, category, rate, bizz))

if __name__ == "__main__":
    CSV_FOLDER = r"d:\Sales\BIZZ_CSV"
    import_csv_to_db(CSV_FOLDER)
