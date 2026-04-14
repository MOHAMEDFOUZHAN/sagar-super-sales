import mysql.connector
from config import Config
import sys

def test_conn():
    print(f"Attempting to connect to {Config.MYSQL_HOST} as {Config.MYSQL_USER}...")
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB,
            connect_timeout=5
        )
        print("Connected!")
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        print(f"Users found: {len(users)}")
        for u in users:
            print(f"User: {u['username']}, Role: {u['role']}, PwdHash: {u['password_hash']}")
        conn.close()
    except mysql.connector.Error as err:
        print(f"Connection Error: {err}")
    except Exception as e:
        print(f"Unexpected Error: {e}")

if __name__ == '__main__':
    test_conn()
