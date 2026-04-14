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

        print(f"Connected to {Config.MYSQL_DB}")

        # 1. Add expense_group to expenses
        cursor.execute("SHOW COLUMNS FROM expenses LIKE 'expense_group'")
        if not cursor.fetchone():
            print("Adding expense_group to expenses table...")
            cursor.execute("ALTER TABLE expenses ADD COLUMN expense_group VARCHAR(50) DEFAULT 'OFFICE'")
        else:
            print("expense_group already exists in expenses.")

        # 2. Create business_charges table
        print("Ensuring business_charges table exists...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS business_charges (
                id INT AUTO_INCREMENT PRIMARY KEY,
                charge_date DATE NOT NULL,
                type VARCHAR(50),
                percent DECIMAL(5, 2),
                amount DECIMAL(10, 2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 3. Create cash_balance table
        print("Ensuring cash_balance table exists...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cash_balance (
                id INT AUTO_INCREMENT PRIMARY KEY,
                balance_date DATE NOT NULL UNIQUE,
                opening_balance DECIMAL(15, 2) DEFAULT 0,
                closing_balance DECIMAL(15, 2) DEFAULT 0,
                actual_closing DECIMAL(15, 2) DEFAULT 0,
                difference DECIMAL(15, 2) DEFAULT 0,
                status VARCHAR(20) DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 4. Create denominations table
        print("Ensuring denominations table exists...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS denominations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                balance_id INT,
                note_value INT,
                count INT,
                FOREIGN KEY (balance_id) REFERENCES cash_balance(id) ON DELETE CASCADE
            )
        """)

        conn.commit()
        print("Database schema updated successfully.")
        conn.close()

    except Exception as e:
        print(f"Error fixing database: {e}")

if __name__ == "__main__":
    fix_database()
