import mysql.connector
from config import Config

def update_schema():
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
        cursor = conn.cursor()

        print("Creating account_entries table...")
        # A unified table for all accounting transactions as per the new requirements
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_entries (
                id INT AUTO_INCREMENT PRIMARY KEY,
                entry_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                major_type ENUM('Asset', 'Liability', 'Equity', 'Revenue', 'Direct Expense', 'Operating Expense') NOT NULL,
                sub_type VARCHAR(100) NOT NULL,
                description TEXT,
                amount DECIMAL(15, 2) NOT NULL,
                payment_type ENUM('Cash', 'UPI', 'Bank', 'Other') DEFAULT 'Cash',
                created_by INT,
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """)

        # Add unique index if necessary or just a created_at for sorting
        cursor.execute("ALTER TABLE account_entries ADD INDEX (entry_date)")
        cursor.execute("ALTER TABLE account_entries ADD INDEX (major_type)")

        conn.commit()
        conn.close()
        print("Schema update successful!")
    except Exception as e:
        print(f"Schema update failed: {e}")

if __name__ == "__main__":
    update_schema()
