import mysql.connector
from config import Config
import sys

def check_users():
    print("Connecting to database...")
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
        print("Connection successful.")
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        print(f"Found {len(users)} users.")
        for user in users:
            print(user)
        conn.close()
    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
    except Exception as e:
        print(f"General Error: {e}")

if __name__ == "__main__":
    check_users()
    print("Done.")
