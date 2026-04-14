import mysql.connector
from config import Config

def check_bill_items():
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
        cursor = conn.cursor()
        cursor.execute("SHOW COLUMNS FROM bill_items")
        columns = [row[0] for row in cursor.fetchall()]
        print("bill_items columns:", columns)
        
        missing = []
        if 'bizz_percent' not in columns: missing.append('bizz_percent')
        if 'bizz_amount' not in columns: missing.append('bizz_amount')
        
        if missing:
            print(f"Missing columns: {missing}")
            for col in missing:
                print(f"Adding {col}...")
                cursor.execute(f"ALTER TABLE bill_items ADD COLUMN {col} DECIMAL(10,2) DEFAULT 0.00")
            conn.commit()
            print("Fixed missing columns.")
        else:
            print("All columns present.")
            
        conn.close()
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    check_bill_items()
