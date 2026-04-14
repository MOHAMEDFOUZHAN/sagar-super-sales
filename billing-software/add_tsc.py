import mysql.connector
from config import Config
import sys

def add_tsc_columns():
    with open('migration_log.txt', 'a') as f:
        f.write("Starting migration...\n")
        try:
            conn = mysql.connector.connect(
                host=Config.MYSQL_HOST,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DB
            )
            cursor = conn.cursor()
            f.write("Connected to DB\n")
            
            try:
                cursor.execute("ALTER TABLE bills ADD COLUMN tsc_percent DECIMAL(5,2) DEFAULT 0")
                f.write("Added tsc_percent column\n")
            except Exception as e:
                f.write(f"tsc_percent issue: {e}\n")

            try:
                cursor.execute("ALTER TABLE bills ADD COLUMN tsc_amount DECIMAL(10,2) DEFAULT 0.00")
                f.write("Added tsc_amount column\n")
            except Exception as e:
                f.write(f"tsc_amount issue: {e}\n")
                
            conn.commit()
            conn.close()
            f.write("Migration finished and committed\n")
        except Exception as e:
            f.write(f"Connection error: {e}\n")

if __name__ == '__main__':
    add_tsc_columns()
