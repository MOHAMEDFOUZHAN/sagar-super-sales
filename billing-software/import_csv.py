import os
import csv
import mysql.connector

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host='127.0.0.1',
            user='root',
            password='',
            database='maple_pro_db'
        )
        return conn
    except Exception as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def import_data():
    conn = get_db_connection()
    if not conn:
        return
    cursor = conn.cursor(dictionary=True)
    
    csv_dir = r"d:\Sales\BIZZ_CSV"
    files = [f for f in os.listdir(csv_dir) if f.endswith('.csv')]
    
    for file in files:
        category = file.replace('.csv', '')
        filepath = os.path.join(csv_dir, file)
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            
            for row in reader:
                # Process in chunks of 4 columns
                for i in range(0, len(row), 4):
                    if i + 1 >= len(row):
                        continue
                    
                    code = row[i].strip()
                    name = row[i+1].strip()
                    
                    if not code or not name:
                        continue
                        
                    rate = 0.0
                    if i+2 < len(row) and row[i+2].strip():
                        try:
                            rate = float(row[i+2].strip())
                        except:
                            pass
                            
                    biz = 0.0
                    if i+3 < len(row) and row[i+3].strip():
                        try:
                            biz = float(row[i+3].strip())
                        except:
                            pass
                            
                    # Default values
                    unit = 'PCS'
                    min_threshold = 25
                    current_stock = 1000
                    
                    # Check if exists
                    cursor.execute("SELECT id FROM products WHERE barcode = %s", (code,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        cursor.execute("""
                            UPDATE products 
                            SET name=%s, category=%s, price=%s, bizz=%s, current_stock=%s
                            WHERE barcode=%s
                        """, (name, category, rate, biz, current_stock, code))
                    else:
                        cursor.execute("""
                            INSERT INTO products (barcode, name, category, price, bizz, unit, min_threshold, current_stock)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (code, name, category, rate, biz, unit, min_threshold, current_stock))
    
    conn.commit()
    conn.close()
    print("Import completed successfully.")

if __name__ == '__main__':
    import_data()
