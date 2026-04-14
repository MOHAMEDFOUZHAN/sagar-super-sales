import mysql.connector
from config import Config

def migrate():
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
        cursor = conn.cursor()
        
        # 1. Add bizz column
        cursor.execute("SHOW COLUMNS FROM products LIKE 'bizz'")
        if not cursor.fetchone():
            print("Adding 'bizz' column...")
            cursor.execute("ALTER TABLE products ADD COLUMN bizz DECIMAL(5, 2) DEFAULT 0.00")
        
        # 2. Add Categories Table
        print("Checking categories table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE
            )
        """)
        
        # 3. Seed Categories from existing products
        cursor.execute("SELECT DISTINCT category FROM products")
        existing_cats = cursor.fetchall()
        for cat in existing_cats:
            if cat[0]:
                try:
                    cursor.execute("INSERT IGNORE INTO categories (name) VALUES (%s)", (cat[0],))
                except:
                    pass

        conn.commit()
        conn.close()
        print("Migration complete.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    migrate()
