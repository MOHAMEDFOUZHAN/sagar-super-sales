from app import get_db_connection

def migrate():
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to DB")
        return
    
    cursor = conn.cursor()
    try:
        # 1. Add source_bill_id to bills table
        print("Checking/Adding source_bill_id to bills...")
        try:
            cursor.execute("ALTER TABLE bills ADD COLUMN source_bill_id INT NULL")
        except:
            print("source_bill_id likely already exists")

        # 2. Add is_correction to bills table (Optional but good for status check)
        # Actually 'status' can be enough, but let's be explicit if needed.
        # User explicitly mentioned source_bill_id column.

        # 3. Create returns_log table
        print("Creating returns_log table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS returns_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                bill_id INT NOT NULL,
                product_name VARCHAR(255) NOT NULL,
                qty DECIMAL(10, 2) NOT NULL,
                amount DECIMAL(10, 2) NOT NULL,
                reason VARCHAR(255),
                returned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (bill_id) REFERENCES bills(id)
            )
        """)
        
        # 4. Update bills total columns to be more flexible for zeroing out if needed
        # (They already exist, just ensuring we can set them to 0)

        conn.commit()
        print("Migration successful")
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
