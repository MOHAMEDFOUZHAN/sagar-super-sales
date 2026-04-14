import mysql.connector
from config import Config

def check_products():
    print("Connecting to check products...")
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
        cursor = conn.cursor()
        cursor.execute("DESCRIBE products")
        columns = cursor.fetchall()
        print("Columns in products table:")
        for col in columns:
            print(col)
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    check_products()
