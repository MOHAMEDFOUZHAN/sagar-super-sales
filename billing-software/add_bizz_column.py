import mysql.connector
from config import Config

def add_column():
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("SHOW COLUMNS FROM products LIKE 'bizz'")
        result = cursor.fetchone()
        
        if not result:
            print("Adding 'bizz' column to products table...")
            cursor.execute("ALTER TABLE products ADD COLUMN bizz DECIMAL(5, 2) DEFAULT 0.00")
            print("Column 'bizz' added successfully.")
        else:
            print("Column 'bizz' already exists.")
            
        conn.commit()
        conn.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    add_column()
