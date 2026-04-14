import mysql.connector
from config import Config

def fix_all():
    print("Connecting to database...")
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
        cursor = conn.cursor()
        
        # Helper to add column if not exists
        def add_column(table, column, definition):
            try:
                cursor.execute(f"DESCRIBE {table}")
                cols = [c[0] for c in cursor.fetchall()]
                if column not in cols:
                    print(f"Adding column {column} to {table}...")
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                    return True
                else:
                    print(f"Column {column} already exists in {table}.")
                    return False
            except Exception as e:
                print(f"Error checking/adding column {column} to {table}: {e}")
                return False

        # 1. Update bills table
        add_column("bills", "discount", "DECIMAL(10, 2) DEFAULT 0.00")
        add_column("bills", "tsc_percent", "DECIMAL(5, 2) DEFAULT 0.00")
        add_column("bills", "tsc_amount", "DECIMAL(10, 2) DEFAULT 0.00")
        add_column("bills", "source_bill_id", "INT NULL")
        
        # 2. Update products table
        add_column("products", "unit", "VARCHAR(20) DEFAULT 'PCS'")
        add_column("products", "expiry_date", "DATE DEFAULT NULL")
        add_column("products", "min_threshold", "INT DEFAULT 10")
        add_column("products", "bizz", "DECIMAL(10, 2) DEFAULT 0.00")

        # 3. Update bill_items table
        add_column("bill_items", "bizz_percent", "DECIMAL(10, 2) DEFAULT 0.00")
        add_column("bill_items", "bizz_amount", "DECIMAL(10, 2) DEFAULT 0.00")

        conn.commit()
        print("Schema update complete.")
        conn.close()
    except Exception as e:
        print(f"Critical Error: {e}")

if __name__ == '__main__':
    fix_all()
