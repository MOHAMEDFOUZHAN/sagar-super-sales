import mysql.connector
from config import Config
import os

SCHEMA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'schema_mysql.sql')

def init_db():
    try:
        # Connect without database first to create it
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD
        )
        cursor = conn.cursor()
        
        # Create Database
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.MYSQL_DB}")
        cursor.execute(f"USE {Config.MYSQL_DB}")
        print(f"Database {Config.MYSQL_DB} ready.")

        # Read and Execute Schema
        with open(SCHEMA_FILE, 'r') as f:
            schema_script = f.read()
        
        # Splitting manually to avoid 'multi' keyword inconsistency in some connector versions
        for statement in schema_script.split(';'):
            if statement.strip():
                cursor.execute(statement)
        
        print("Schema applied.")

        # Seed Data
        # 1. Clear existing data for a fresh start
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        cursor.execute("TRUNCATE TABLE users")
        cursor.execute("TRUNCATE TABLE products")
        cursor.execute("TRUNCATE TABLE bills")
        cursor.execute("TRUNCATE TABLE bill_items")
        cursor.execute("TRUNCATE TABLE expenses")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

        # 2. Users
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)", 
                       ('counter', '123', 'sales'))
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)", 
                       ('admin', 'admin123', 'admin'))
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)", 
                       ('accountant', 'account123', 'account'))

        # 3. Products (with Barcodes)
        products = [
            ('1001', 'Nilgiri Oil 60ml', 'Oils', 130.00, 50, 'PCS'),
            ('1002', 'Green Tea Premium', 'Tea', 250.00, 100, 'PKT'),
            ('1003', 'Dark Choco 100g', 'Choco', 80.00, 30, 'PCS'),
            ('1004', 'Cardamom 50g', 'Spices', 320.00, 20, 'PKT')
        ]
        cursor.executemany("INSERT INTO products (barcode, name, category, price, current_stock, unit) VALUES (%s, %s, %s, %s, %s, %s)", products)

        conn.commit()
        conn.close()
        print("Database initialized and seeded successfully.")

    except mysql.connector.Error as err:
        print(f"MySQL Error: {err}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    init_db()
