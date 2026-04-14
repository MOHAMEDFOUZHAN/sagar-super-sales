import mysql.connector
import sys
import os

billing_software_path = os.path.join(r'd:\Sales', 'billing-software')
sys.path.append(billing_software_path)

try:
    from config import Config
except ImportError:
    class Config:
        MYSQL_HOST = '127.0.0.1'; MYSQL_USER = 'root'; MYSQL_PASSWORD = ''; MYSQL_DB = 'maple_pro_db'

try:
    conn = mysql.connector.connect(
        host=Config.MYSQL_HOST, user=Config.MYSQL_USER, 
        password=Config.MYSQL_PASSWORD, database=Config.MYSQL_DB
    )
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM bills WHERE DATE(bill_date) = '2026-04-11'")
    count = cursor.fetchone()[0]
    print(f"Total bills for 2026-04-11: {count}")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
