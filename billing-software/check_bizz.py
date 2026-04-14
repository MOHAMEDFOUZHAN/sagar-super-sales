import mysql.connector
from config import Config

def check():
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
        cursor = conn.cursor()
        
        print("Checking Bill Items Bizz Distribution:")
        cursor.execute("SELECT bizz_percent, SUM(bizz_amount) FROM bill_items GROUP BY bizz_percent")
        print(cursor.fetchall())
        
        print("\nChecking Products Bizz Distribution:")
        cursor.execute("SELECT bizz, COUNT(*) FROM products GROUP BY bizz")
        print(cursor.fetchall())
        
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    check()
