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

        print("Updating users table role column...")
        # MySQL ALter table to update enum
        cursor.execute("ALTER TABLE users MODIFY COLUMN role ENUM('admin', 'sales', 'account') DEFAULT 'sales'")
        
        print("Adding accountant user...")
        cursor.execute("INSERT IGNORE INTO users (username, password_hash, role) VALUES (%s, %s, %s)", 
                       ('accountant', 'account123', 'account'))
        
        conn.commit()
        conn.close()
        print("Migration successful!")
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
