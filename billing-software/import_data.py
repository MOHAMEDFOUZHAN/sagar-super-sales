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
    cursor = conn.cursor(dictionary=True)
    
    # Pre-load existing products to avoid barcode collisions and maintain consistency
    cursor.execute("SELECT id, barcode, name FROM products")
    existing_products = {p['name'].strip().upper(): p['barcode'] for p in cursor.fetchall()}
    
    # Get max current barcode to continue sequence if needed
    cursor.execute("SELECT MAX(CAST(barcode AS UNSIGNED)) as max_bc FROM products WHERE barcode REGEXP '^[0-9]+$'")
    res = cursor.fetchone()
    current_max = res['max_bc'] if res and res['max_bc'] else 0
    
    files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]
    
    for filename in files:
        category = os.path.splitext(filename)[0].upper()
        file_path = os.path.join(folder_path, filename)
        print(f"Importing {category}...")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)
            
            for row in reader:
                if len(row) >= 4:
                    current_max = process_item(cursor, row[0], row[1], row[2], row[3], category, existing_products, current_max)
                if len(row) >= 8:
                    current_max = process_item(cursor, row[4], row[5], row[6], row[7], category, existing_products, current_max)
                    
    conn.commit()
    conn.close()
    print(" Import Complete!")

def process_item(cursor, csv_code, name, rate, bizz, category, existing_products, current_max):
    if not csv_code or not name:
        return current_max

    name = name.strip()
    name_upper = name.upper()
    rate = clean_money(rate)
    bizz = clean_money(bizz)
    
    # Use existing barcode if product already exists by name
    if name_upper in existing_products:
        barcode = existing_products[name_upper]
    else:
        # Generate new sequential 3-digit barcode
        current_max += 1
        barcode = f"{current_max:03d}"
        existing_products[name_upper] = barcode
    
    # Insert or Update by barcode
    cursor.execute("""
        INSERT INTO products (barcode, name, category, price, bizz, current_stock)
        VALUES (%s, %s, %s, %s, %s, 100)
        ON DUPLICATE KEY UPDATE
        name = VALUES(name),
        price = VALUES(price),
        bizz = VALUES(bizz),
        category = VALUES(category)
    """, (barcode, name, category, rate, bizz))
    
    return current_max

if __name__ == "__main__":
    CSV_FOLDER = r"d:\Sales\BIZZ_CSV"
    import_csv_to_db(CSV_FOLDER)
