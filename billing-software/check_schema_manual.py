import mysql.connector
from config import Config

def check_bills():
    print("Connecting to check bills...")
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
        cursor = conn.cursor()
        cursor.execute("DESCRIBE bills")
        columns = cursor.fetchall()
        print("Columns in bills table:")
        for col in columns:
            print(col)
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    check_bills()
