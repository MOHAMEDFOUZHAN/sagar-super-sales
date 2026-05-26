import mysql.connector
import psycopg2
import sys
import os
import getpass

# Import Config to read local database settings
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import Config

SUPABASE_PROJECT_ID = "ibpiixejgrxpejivdekc"

# Order of tables to migrate to prevent Foreign Key constraints issues
TABLES_MIGRATION_ORDER = [
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

def migrate():
    print("==================================================")
    print("   LOCAL MYSQL -> SUPABASE CLOUD DATA MIGRATION")
    print("==================================================")
    
    # 1. Ask for Supabase Password securely
    print(f"Supabase Project ID: {SUPABASE_PROJECT_ID}")
    supabase_password = getpass.getpass("Enter your Supabase Database Password: ").strip()
    if not supabase_password:
        print("[ERROR] Password cannot be empty.")
        return
    # 2. Establish connections
    print("\nConnecting to local MySQL (Laragon)...")
    try:
        mysql_conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB,
            port=Config.MYSQL_PORT
        )
        mysql_cursor = mysql_conn.cursor(dictionary=True)
        print("[SUCCESS] Local MySQL database connected.")
    except Exception as e:
        print(f"[FAILED] Could not connect to local MySQL: {e}")
        return

    print("Connecting to Supabase PostgreSQL...")
    try:
        pg_conn = psycopg2.connect(
            host=f"db.{SUPABASE_PROJECT_ID}.supabase.co",
            port=6543,
            database="postgres",
            user="postgres",
            password=supabase_password,
            connect_timeout=10
        )
        pg_cursor = pg_conn.cursor()
        print("[SUCCESS] Supabase PostgreSQL connected.")
    except Exception as e:
        print(f"[FAILED] Could not connect to Supabase: {e}")
        mysql_conn.close()
        return

    # 3. Create tables and schemas on Supabase
    print("\n[1/3] Setting up database schema and structures on Supabase...")
    schema_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "supabase_schema.sql")
    if not os.path.exists(schema_file_path):
        print(f"[ERROR] Schema file not found at: {schema_file_path}")
        mysql_conn.close()
        pg_conn.close()
        return

    try:
        with open(schema_file_path, 'r') as f:
            sql_schema = f.read()
        
        # PostgreSQL can run multiple commands in a single execute block
        pg_cursor.execute(sql_schema)
        pg_conn.commit()
        print("[SUCCESS] Table schemas and indexes created/verified in Supabase.")
    except Exception as e:
        print(f"[FAILED] Schema setup failed: {e}")
        pg_conn.rollback()
        mysql_conn.close()
        pg_conn.close()
        return

    # 4. Migrate Data
    print("\n[2/3] Transferring data table by table...")
    for table_name in TABLES_MIGRATION_ORDER:
        try:
            print(f"  * Migrating table '{table_name}'...")
            
            # Fetch data from MySQL
            mysql_cursor.execute(f"SELECT * FROM {table_name}")
            rows = mysql_cursor.fetchall()
            
            if not rows:
                print(f"    [INFO] Table '{table_name}' has 0 records. Skipped.")
                continue

            # Get columns dynamically
            columns = list(rows[0].keys())
            
            # We want to clear the target table first to ensure a clean sync (using TRUNCATE CASCADE)
            pg_cursor.execute(f"TRUNCATE TABLE {table_name} CASCADE;")
            
            # Construct insert query for PostgreSQL
            # PostgreSQL uses %s for placeholders
            col_names = ", ".join(columns)
            placeholders = ", ".join(["%s"] * len(columns))
            insert_query = f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})"
            
            # Prepare rows values
            values_to_insert = []
            for row in rows:
                row_values = []
                for col in columns:
                    val = row[col]
                    # Handle enum conversions or boolean flags if necessary
                    row_values.append(val)
                values_to_insert.append(tuple(row_values))

            # Execute bulk insertion
            pg_cursor.executemany(insert_query, values_to_insert)
            pg_conn.commit()
            print(f"    [SUCCESS] Transferred {len(rows)} rows into Supabase '{table_name}'.")

        except Exception as e:
            print(f"    [ERROR] Migrating table '{table_name}': {e}")
            pg_conn.rollback()
            # We don't break immediately to attempt migrating other tables if one fails

    # 5. Synchronize Serial Primary Key Sequences
    print("\n[3/3] Synchronizing primary key sequence counters...")
    for table_name in TABLES_MIGRATION_ORDER:
        # Tables that have auto-incrementing serial columns need their sequences updated
        if table_name in ["bill_sequences", "daily_position_list"]: 
            continue # Non-serial primary keys
            
        try:
            # This PostgreSQL query checks the maximum ID and sets the next sequence index to max(id) + 1
            seq_reset_query = f"""
                SELECT setval(
                    pg_get_serial_sequence('{table_name}', 'id'), 
                    coalesce(max(id), 1)
                ) FROM {table_name};
            """
            pg_cursor.execute(seq_reset_query)
            pg_conn.commit()
            print(f"  [OK] Reset sequence for '{table_name}' successfully.")
        except Exception as e:
            # Some tables might not have an integer 'id' primary key or no sequence
            pg_conn.rollback()

    # Close everything
    mysql_conn.close()
    pg_conn.close()
    
    print("\n==================================================")
    print("   [DONE] MIGRATION PROCESS SUCCESSFULLY COMPLETED!")
    print("==================================================")

if __name__ == '__main__':
    migrate()
