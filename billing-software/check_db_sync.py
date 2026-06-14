import mysql.connector
import psycopg2
from mysql.connector import errorcode
import sys
import os

# Configuration
MYSQL_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '',
    'database': 'maple_pro_db',
    'port': 3306
}

SUPABASE_CONFIG = {
    'host': 'db.ibpiixejgrxpejivdekc.supabase.co',
    'port': 6543,
    'database': 'postgres',
    'user': 'postgres',
    'password': 'Fouzfif@3110'
}

TABLES_TO_CHECK = [
    "users",
    "categories",
    "products",
    "expenses",
    "audit_logs",
    "cash_balance",
    "bill_sequences",
    "bills",
    "bill_items",
    "stock_movements",
    "returns_log",
    "denominations",
    "account_entries",
    "daily_position_list"
]

def get_mysql_schema(cursor, table_name):
    try:
        cursor.execute(f"DESCRIBE {table_name}")
        return {row[0]: row[1] for row in cursor.fetchall()}
    except mysql.connector.Error as err:
        return None

def get_pg_schema(cursor, table_name):
    try:
        cursor.execute(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}'
            AND table_schema = 'public'
        """)
        return {row[0]: row[1] for row in cursor.fetchall()}
    except Exception as e:
        return None

def check_sync():
    print("==================================================")
    print("   DATABASE SCHEMA CONSISTENCY CHECK")
    print("==================================================")

    # 1. Connect to Local MySQL
    print("Connecting to local MySQL...")
    try:
        mysql_conn = mysql.connector.connect(**MYSQL_CONFIG)
        mysql_cursor = mysql_conn.cursor()
        print("[SUCCESS] Local MySQL connected.")
    except mysql.connector.Error as err:
        print(f"[FAILED] MySQL connection: {err}")
        return

    # 2. Connect to Cloud PostgreSQL (Supabase)
    print("Connecting to cloud PostgreSQL (Supabase)...")
    try:
        pg_conn = psycopg2.connect(**SUPABASE_CONFIG)
        pg_cursor = pg_conn.cursor()
        print("[SUCCESS] Cloud PostgreSQL connected.")
    except Exception as e:
        print(f"[FAILED] PostgreSQL connection: {e}")
        mysql_conn.close()
        return

    # 3. Compare Tables
    print("\nComparing table schemas:")
    mismatches = 0
    for table in TABLES_TO_CHECK:
        print(f"\nChecking table: {table}")
        mysql_schema = get_mysql_schema(mysql_cursor, table)
        pg_schema = get_pg_schema(pg_cursor, table)

        if mysql_schema is None:
            print(f"  [ERROR] Table '{table}' MISSING in Local MySQL.")
            mismatches += 1
            continue
        
        if not pg_schema:
            print(f"  [ERROR] Table '{table}' MISSING in Cloud PostgreSQL.")
            mismatches += 1
            continue

        # Compare column names
        mysql_cols = set(mysql_schema.keys())
        pg_cols = set(pg_schema.keys())

        if mysql_cols == pg_cols:
            print(f"  [OK] Columns match ({len(mysql_cols)} columns).")
        else:
            mismatches += 1
            missing_in_pg = mysql_cols - pg_cols
            missing_in_mysql = pg_cols - mysql_cols
            if missing_in_pg:
                print(f"  [MISMATCH] Missing in Cloud: {missing_in_pg}")
            if missing_in_mysql:
                print(f"  [MISMATCH] Missing in Local: {missing_in_mysql}")

    print("\n==================================================")
    if mismatches == 0:
        print("   [DONE] ALL SCHEMAS ARE CONSISTENT!")
    else:
        print(f"   [DONE] FOUND {mismatches} SCHEMA DISCREPANCIES.")
    print("==================================================")

    mysql_conn.close()
    pg_conn.close()

if __name__ == '__main__':
    check_sync()
