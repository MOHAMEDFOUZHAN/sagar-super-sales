import mysql.connector
from config import Config

def fix_db():
    import time
    for i in range(5):
        try:
            conn = mysql.connector.connect(
                host='localhost',
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DB,
                connect_timeout=10
            )
            print(f"Connected on attempt {i+1}")
            break
        except Exception as e:
            print(f"Attempt {i+1} failed: {e}")
            if i < 4:
                time.sleep(2)
            else:
                print("Max retries reached. Exiting.")
                return
    
    try:
        cursor = conn.cursor()
        
        # 1. Create categories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                description TEXT,
                icon VARCHAR(50)
            )
        """)
        print("Checked categories table.")

        # 2. Fix products table columns
        cursor.execute("DESCRIBE products")
        columns = [col[0] for col in cursor.fetchall()]

        if 'expiry_date' not in columns:
            cursor.execute("ALTER TABLE products ADD COLUMN expiry_date DATE DEFAULT NULL")
            print("Added expiry_date.")
        
        if 'bizz' not in columns:
            cursor.execute("ALTER TABLE products ADD COLUMN bizz DECIMAL(10,2) DEFAULT 0")
            print("Added bizz.")
            
        if 'min_threshold' not in columns:
            cursor.execute("ALTER TABLE products ADD COLUMN min_threshold INT DEFAULT 25")
            print("Added min_threshold to products.")

        # 3. Fix bill_items table columns
        cursor.execute("DESCRIBE bill_items")
        columns_bi = [col[0] for col in cursor.fetchall()]

        if 'bizz_percent' not in columns_bi:
            cursor.execute("ALTER TABLE bill_items ADD COLUMN bizz_percent DECIMAL(10,2) DEFAULT 0")
            print("Added bizz_percent to bill_items.")
        
        if 'bizz_amount' not in columns_bi:
            cursor.execute("ALTER TABLE bill_items ADD COLUMN bizz_amount DECIMAL(10,2) DEFAULT 0")
            print("Added bizz_amount to bill_items.")

        conn.commit()
        conn.close()
        print("Database schema synchronization complete.")
    except Exception as e:
        print(f"Error fixing database: {e}")

if __name__ == "__main__":
    fix_db()
