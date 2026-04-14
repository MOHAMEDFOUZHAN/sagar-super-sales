import mysql.connector
from config import Config

def fix_all_tables():
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
        cursor = conn.cursor()
        print("Connected to database.")

        # 1. Create cash_balance table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cash_balance (
                id INT AUTO_INCREMENT PRIMARY KEY,
                balance_date DATE NOT NULL UNIQUE,
                opening_balance DECIMAL(10, 2) DEFAULT 0,
                actual_closing DECIMAL(10, 2) DEFAULT 0,
                closing_balance DECIMAL(10, 2) DEFAULT 0,
                difference DECIMAL(10, 2) DEFAULT 0,
                status VARCHAR(20) DEFAULT 'OPEN'
            )
        """)
        print("Table 'cash_balance' checked/created.")

        # 2. Create denominations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS denominations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                balance_id INT NOT NULL,
                note_value INT NOT NULL,
                count INT DEFAULT 0,
                FOREIGN KEY (balance_id) REFERENCES cash_balance(id) ON DELETE CASCADE
            )
        """)
        print("Table 'denominations' checked/created.")

        # 3. Double check bills for tsc columns (just in case)
        cursor.execute("SHOW COLUMNS FROM bills LIKE 'tsc_percent'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE bills ADD COLUMN tsc_percent DECIMAL(5,2) DEFAULT 0")
            cursor.execute("ALTER TABLE bills ADD COLUMN tsc_amount DECIMAL(10,2) DEFAULT 0.00")
            print("Added TSC columns to 'bills'.")

        # 4. Double check bill_items for bizz columns
        cursor.execute("SHOW COLUMNS FROM bill_items LIKE 'bizz_percent'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE bill_items ADD COLUMN bizz_percent DECIMAL(10,2) DEFAULT 0.00")
            cursor.execute("ALTER TABLE bill_items ADD COLUMN bizz_amount DECIMAL(10,2) DEFAULT 0.00")
            print("Added Bizz columns to 'bill_items'.")

        conn.commit()
        conn.close()
        print("Migration successful! All tables and columns are ready.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    fix_all_tables()
