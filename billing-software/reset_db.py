import mysql.connector
from config import Config

def get_db_connection():
    return mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB
    )

def reset_manager():
    print("\n--- DATABASE RESET MANAGER ---")
    print("1. Delete ALL PRODUCTS (Inventory)")
    print("2. Delete ALL BILLS (Sales History)")
    print("3. Delete ALL EXPENSES")
    print("4. Delete EVERYTHING (Fresh Start)")
    print("5. Cancel")
    
    choice = input("\nEnter your choice (1-5): ")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    
    try:
        if choice == '1':
            confirm = input("Are you sure you want to delete ALL PRODUCTS? (yes/no): ")
            if confirm.lower() == 'yes':
                cursor.execute("TRUNCATE TABLE products")
                print("✅ All products have been deleted.")
        
        elif choice == '2':
            confirm = input("Are you sure you want to delete ALL SALES HISTORY? (yes/no): ")
            if confirm.lower() == 'yes':
                cursor.execute("TRUNCATE TABLE bills")
                cursor.execute("TRUNCATE TABLE bill_items")
                print("✅ All bills and sales items have been deleted.")

        elif choice == '3':
            confirm = input("Are you sure you want to delete ALL EXPENSES? (yes/no): ")
            if confirm.lower() == 'yes':
                cursor.execute("TRUNCATE TABLE expenses")
                print("✅ All expenses have been deleted.")

        elif choice == '4':
            confirm = input("⚠️ CRITICAL: This will wipe EVERYTHING (Products, Bills, Expenses, Users). Continue? (yes/no): ")
            if confirm.lower() == 'yes':
                cursor.execute("TRUNCATE TABLE products")
                cursor.execute("TRUNCATE TABLE bills")
                cursor.execute("TRUNCATE TABLE bill_items")
                cursor.execute("TRUNCATE TABLE expenses")
                cursor.execute("TRUNCATE TABLE users")
                
                # Re-seed default admin/counter
                cursor.execute("INSERT INTO users (username, password_hash, role) VALUES ('admin', 'admin123', 'admin')")
                cursor.execute("INSERT INTO users (username, password_hash, role) VALUES ('counter', '123', 'sales')")
                print("✅ Database wiped and reset to factory settings (Users restored).")

        else:
            print("Action cancelled.")

        conn.commit()
        
    except Exception as e:
        print(f"❌ An error occurred: {str(e)}")
        
    finally:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.close()

if __name__ == "__main__":
    reset_manager()
