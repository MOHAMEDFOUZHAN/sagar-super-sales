from app import get_db_connection
import mysql.connector

def final_migration():
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to DB")
        return
    
    cursor = conn.cursor()
    try:
        # 1. Ensure columns exist in bills table
        print("Updating bills table schema...")
        columns_to_add = [
            ("discount", "DECIMAL(10, 2) DEFAULT 0.00"),
            ("source_bill_id", "INT NULL"),
            ("tsc_percent", "DECIMAL(5, 2) DEFAULT 0.00"),
            ("tsc_amount", "DECIMAL(10, 2) DEFAULT 0.00")
        ]
        
        for col_name, col_def in columns_to_add:
            try:
                cursor.execute(f"ALTER TABLE bills ADD COLUMN {col_name} {col_def}")
                print(f"Added column: {col_name}")
            except Exception as e:
                print(f"Column {col_name} probably already exists.")

        # 2. Create stock_transfers table
        print("Ensuring stock_transfers table exists...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_transfers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                transfer_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                product_barcode VARCHAR(50),
                product_name VARCHAR(255),
                qty DECIMAL(10, 2),
                from_location VARCHAR(100),
                to_location VARCHAR(100),
                pushed_by VARCHAR(100)
            )
        """)

        # 3. Create returns_log table if not exists
        print("Ensuring returns_log table exists...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS returns_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                bill_id INT NOT NULL,
                product_name VARCHAR(255) NOT NULL,
                qty DECIMAL(10, 2) NOT NULL,
                amount DECIMAL(10, 2) NOT NULL,
                reason VARCHAR(255),
                returned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        print("Backend data structures are fully synchronized.")
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    final_migration()
