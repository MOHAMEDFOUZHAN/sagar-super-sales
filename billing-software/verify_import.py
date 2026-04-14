import mysql.connector
from config import Config

def check_counts():
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
        cursor = conn.cursor()
        cursor.execute("SELECT category, COUNT(*) FROM products GROUP BY category")
        rows = cursor.fetchall()
        print("Product counts by category:")
        for row in rows:
            print(f"{row[0]}: {row[1]}")
        cursor.execute("SELECT COUNT(*) FROM products")
        total = cursor.fetchone()[0]
        print(f"Total Products: {total}")
        conn.close()
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    check_counts()
