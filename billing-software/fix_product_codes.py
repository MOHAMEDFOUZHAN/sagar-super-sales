import mysql.connector
from config import Config

def migrate_product_codes():
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
        cursor = conn.cursor(dictionary=True)

        print(f"Connected to {Config.MYSQL_DB}")

        # Fetch all products ordered by original barcode (or ID)
        cursor.execute("SELECT id, barcode, name FROM products ORDER BY barcode ASC")
        products = cursor.fetchall()

        print(f"Found {len(products)} products. Starting migration to 3-digit codes...")

        # We will use a mapping to update other tables
        mapping = {}

        for i, p in enumerate(products, 1):
            new_code = f"{i:03d}"  # 001, 002, ...
            old_code = p['barcode']
            product_id = p['id']
            
            mapping[old_code] = new_code
            
            # Update product barcode
            cursor.execute("UPDATE products SET barcode = %s WHERE id = %s", (new_code, product_id))
            print(f"Updated: {p['name']} ({old_code} -> {new_code})")

        # Update referencing tables
        print("\nUpdating referencing tables...")
        
        tables_to_update = [
            ('bill_items', 'product_code'),
            ('returns_log', 'product_code'),
            ('stock_transfers', 'product_barcode'),
            ('daily_position_list', 'barcode')
        ]

        for table, col in tables_to_update:
            cursor.execute(f"SHOW TABLES LIKE '{table}'")
            if cursor.fetchone():
                print(f"Processing table: {table}")
                for old_bc, new_bc in mapping.items():
                    if old_bc:
                        cursor.execute(f"UPDATE {table} SET {col} = %s WHERE {col} = %s", (new_bc, old_bc))
            else:
                print(f"Table {table} not found, skipping.")

        conn.commit()
        print("\nMigration completed successfully!")
        conn.close()

    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    migrate_product_codes()
