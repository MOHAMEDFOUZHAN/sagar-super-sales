import mysql.connector
from config import Config

def check_bill_items():
    print("Connecting to check bill_items...")
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
        cursor = conn.cursor()
        cursor.execute("DESCRIBE bill_items")
        columns = cursor.fetchall()
        print("Columns in bill_items table:")
        for col in columns:
            print(col)
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    check_bill_items()
