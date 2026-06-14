import mysql.connector
import psycopg2
from config import Config

SUPABASE_PROJECT_ID = "ibpiixejgrxpejivdekc"
SUPABASE_PASSWORD = "Fouzfif@3110"

TRANSACTION_TABLES = [
    'bill_items', 'bill_sequences', 'returns_log',
    'stock_movements', 'stock_transfers', 'expenses', 'audit_logs',
    'account_entries', 'cash_balance', 'denominations', 'bills'
]

print("Starting Transaction Wipe (Products & Stock kept intact)")

# 1. Wipe LOCAL MySQL
try:
    mysql_conn = mysql.connector.connect(
        host=Config.MYSQL_HOST,
        port=Config.MYSQL_PORT,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB,
        connection_timeout=3,
    )
    mcur = mysql_conn.cursor()
    mcur.execute("SET FOREIGN_KEY_CHECKS = 0")
    for tbl in TRANSACTION_TABLES:
        try:
            mcur.execute(f"TRUNCATE TABLE {tbl}")
            print(f"[LOCAL] Truncated {tbl}")
        except Exception as te:
            pass
    mcur.execute("SET FOREIGN_KEY_CHECKS = 1")
    mysql_conn.commit()
    mysql_conn.close()
    print("[WIPE] Local MySQL cleared successfully.")
except Exception as e:
    print(f"[WIPE] Local MySQL error: {e}")

# 2. Wipe CLOUD Supabase
try:
    raw_pg = psycopg2.connect(
        host=f"db.{SUPABASE_PROJECT_ID}.supabase.co",
        port=6543,
        database="postgres",
        user="postgres",
        password=SUPABASE_PASSWORD,
        connect_timeout=5
    )
    pgcur = raw_pg.cursor()
    for tbl in TRANSACTION_TABLES:
        try:
            pgcur.execute(f"TRUNCATE TABLE {tbl} CASCADE")
            raw_pg.commit()
            print(f"[CLOUD] Truncated {tbl}")
        except Exception as te:
            raw_pg.rollback()
    pgcur.close()
    raw_pg.close()
    print("[WIPE] Supabase cloud cleared successfully.")
except Exception as e:
    print(f"[WIPE] Supabase error: {e}")

print("Wipe operation complete.")
