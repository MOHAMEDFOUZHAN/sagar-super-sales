import psycopg2
import time
import os

CLOUD_DB_URL = "postgresql://neondb_owner:npg_6xQaYTgvCJ7G@ep-spring-recipe-a17qufnw-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"

def test_cloud_db():
    print("==================================================")
    print("   NEON CLOUD POSTGRESQL CONNECTION TEST")
    print("==================================================")
    
    print(f"Connecting to:\n{CLOUD_DB_URL.split('@')[1]}\n")
    
    # 1. Measure connection establishment latency
    start_time = time.time()
    try:
        conn = psycopg2.connect(CLOUD_DB_URL, connect_timeout=5)
        conn_time = (time.time() - start_time) * 1000
        print(f"[SUCCESS] Connected to cloud database in {conn_time:.2f} ms")
    except Exception as e:
        print(f"[FAILED] Could not connect to cloud database.")
        print(f"Error: {e}")
        return
        
    # 2. Run a simple round-trip time (RTT) test query
    try:
        cursor = conn.cursor()
        
        # Test Query 1: Simple SELECT 1 (Database engine response speed)
        rtt_start = time.time()
        cursor.execute("SELECT 1;")
        cursor.fetchone()
        rtt_time = (time.time() - rtt_start) * 1000
        print(f"[SUCCESS] Simple query RTT (SELECT 1): {rtt_time:.2f} ms")
        
        # Test Query 2: Retrieve list of user-defined tables in Neon
        print("\nRetrieving tables in the cloud database:")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        if tables:
            print("Found the following tables:")
            for index, table in enumerate(tables, 1):
                print(f"  {index}. {table[0]}")
        else:
            print("No public tables found in the database. Schema is currently empty.")
            
        cursor.close()
        conn.close()
        print("\nConnection closed successfully.")
        
    except Exception as e:
        print(f"[ERROR] Executing query: {e}")
        try:
            conn.close()
        except:
            pass

if __name__ == '__main__':
    test_cloud_db()
