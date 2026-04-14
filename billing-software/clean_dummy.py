import mysql.connector
from config import Config

def clean_dummy():
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
        cursor = conn.cursor()
        # Delete the 4 dummy products
        cursor.execute("DELETE FROM products WHERE barcode IN ('1001', '1002', '1003', '1004')")
        print(f"Removed {cursor.rowcount} dummy products.")
        conn.commit()
        conn.close()
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    clean_dummy()
