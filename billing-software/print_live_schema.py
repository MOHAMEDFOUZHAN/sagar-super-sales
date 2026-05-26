import mysql.connector
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import Config

def print_live_schema():
    conn = mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB,
        port=Config.MYSQL_PORT
    )
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    
    print("==================================================")
    print("      LIVE LOCAL MYSQL DATABASE SCHEMA")
    print("==================================================")
    
    for table in tables:
        table_name = table[0]
        print(f"\nTable: {table_name}")
        cursor.execute(f"DESCRIBE {table_name}")
        columns = cursor.fetchall()
        for col in columns:
            col_name, col_type, null, key, default, extra = col
            key_str = f" ({key})" if key else ""
            default_str = f" DEFAULT {default}" if default is not None else ""
            extra_str = f" {extra}" if extra else ""
            print(f"  - {col_name}: {col_type}{key_str}{default_str}{extra_str}")
            
    conn.close()

if __name__ == '__main__':
    print_live_schema()
