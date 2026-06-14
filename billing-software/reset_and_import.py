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

def clean_money(value):
    if not value or str(value).strip() == '':
        return 0.0
    try:
        # Remove anything that isn't a digit or decimal point
        cleaned = ''.join(c for c in str(value) if c.isdigit() or c == '.')
        return float(cleaned)
    except:
        return 0.0

def reset_and_import(folder_path):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("Wiping existing products...")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    cursor.execute("TRUNCATE TABLE products")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    print("Database wiped.")

    total_added = 0
    files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]
    files.sort()

    for filename in files:
        category = os.path.splitext(filename)[0].upper()
        file_path = os.path.join(folder_path, filename)
        print(f"Importing {category}...")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None) # Skip header
            
            for row in reader:
                # Set 1: Col 0-3 (Barcode is index 0)
                if len(row) >= 2 and row[1].strip() and row[0].strip():
                    barcode = row[0].strip()
                    process_item(cursor, barcode, row[1], row[2], row[3] if len(row) > 3 else '', category)
                    total_added += 1
                
                # Set 2: Col 4-7 (Barcode is index 4)
                if len(row) >= 6 and row[5].strip() and row[4].strip():
                    barcode = row[4].strip()
                    process_item(cursor, barcode, row[5], row[6], row[7] if len(row) > 7 else '', category)
                    total_added += 1
                    
    conn.commit()
    conn.close()
    print(f"Import Complete! Total products added: {total_added}")

def process_item(cursor, barcode, name, rate, bizz, category):
    name = name.strip()
    rate = clean_money(rate)
    bizz = clean_money(bizz)
    
    # If barcode has only 3 digits, add '1' in front
    if len(barcode) == 3 and barcode.isdigit():
        barcode = "1" + barcode
    
    cursor.execute("""
        INSERT INTO products (barcode, name, category, price, bizz, current_stock, unit)
        VALUES (%s, %s, %s, %s, %s, 100, 'PCS')
    """, (barcode, name, category, rate, bizz))

if __name__ == "__main__":
    CSV_FOLDER = r"D:\Sales\BIZZ_CSV"
    reset_and_import(CSV_FOLDER)
