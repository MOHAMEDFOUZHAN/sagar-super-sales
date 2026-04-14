import mysql.connector
from config import Config

def force_fix():
    print("Starting force fix...")
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD
        )
        cursor = conn.cursor()
        
        # Ensure DB exists
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.MYSQL_DB}")
        cursor.execute(f"USE {Config.MYSQL_DB}")
        
        # Update users table role (adding 'account' to enum)
        print("Updating role enum...")
        try:
            cursor.execute("ALTER TABLE users MODIFY COLUMN role ENUM('admin', 'sales', 'account') DEFAULT 'sales'")
        except Exception as e:
            print(f"Role update note: {e}")
            
        # Add accountant user
        print("Adding accountant user...")
        cursor.execute("INSERT IGNORE INTO users (username, password_hash, role) VALUES (%s, %s, %s)", 
                       ('accountant', 'account123', 'account'))
        
        conn.commit()
        print("Done!")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    force_fix()
