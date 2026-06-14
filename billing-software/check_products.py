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
        cursor.execute("SELECT barcode, name FROM products LIMIT 20")
        products = cursor.fetchall()
        print("\nFirst 20 products:")
        for p in products:
            print(f"Barcode: {p[0]}, Name: {p[1]}")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    check_products()
