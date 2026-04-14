import mysql.connector
from config import Config

def fix_database():
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
        cursor = conn.cursor()
        
        print("Starting database fix...")
        
        # 1. Add missing columns to bills table
        print("Checking/Adding 'discount' and 'source_bill_id' to 'bills' table...")
        
        # Check existing columns
        cursor.execute("DESCRIBE bills")
        cols = [col[0] for col in cursor.fetchall()]

        if 'discount' not in cols:
            print("Adding 'discount' column...")
            cursor.execute("ALTER TABLE bills ADD COLUMN discount DECIMAL(10, 2) DEFAULT 0.00")
            
        if 'source_bill_id' not in cols:
            print("Adding 'source_bill_id' column...")
            cursor.execute("ALTER TABLE bills ADD COLUMN source_bill_id INT")
            
        print("Bills table updated.")
            
        # 2. Add 'expense_group' to expenses table if missing
        cursor.execute("DESCRIBE expenses")
        exp_cols = [col[0] for col in cursor.fetchall()]
        if 'expense_group' not in exp_cols:
            print("Adding 'expense_group' column to expenses...")
            cursor.execute("ALTER TABLE expenses ADD COLUMN expense_group VARCHAR(50) DEFAULT 'OFFICE'")
            
        # 2. Add returns_log table if it doesn't exist
        try:
            print("Checking/Creating 'returns_log' table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS returns_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    bill_id INT,
                    product_name VARCHAR(100),
                    qty DECIMAL(10, 2),
                    amount DECIMAL(10, 2),
                    reason TEXT,
                    return_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
                )
            """)
            print("Returns_log table ready.")
        except Exception as e:
            print(f"Returns log error: {e}")

        conn.commit()
        conn.close()
        print("Database fix completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_database()
