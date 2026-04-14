import mysql.connector
from config import Config

def list_dbs():
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD
        )
        cursor = conn.cursor()
        cursor.execute("SHOW DATABASES")
        dbs = [row[0] for row in cursor.fetchall()]
        print("Databases found:", dbs)
        
        if Config.MYSQL_DB in dbs:
            print(f"Database {Config.MYSQL_DB} exists.")
            conn.database = Config.MYSQL_DB
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            print("Tables found:", tables)
        else:
            print(f"Database {Config.MYSQL_DB} NOT found.")
            
        conn.close()
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    list_dbs()
