import mysql.connector
from config import Config
import sys

def test_conn():
    print(f"Testing connection to {Config.MYSQL_HOST}...")
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            connect_timeout=5
        )
        print("Connected!")
        cursor = conn.cursor()
        cursor.execute("SHOW DATABASES")
        dbs = cursor.fetchall()
        print("DBs:", [d[0] for d in dbs])
        conn.close()
    except Exception as e:
        print("Failed:", e)

if __name__ == "__main__":
    test_conn()
