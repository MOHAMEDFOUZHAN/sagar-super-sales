import mysql.connector
from config import Config
import os

def verify_users():
    results = []
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB
        )
        cursor = conn.cursor(dictionary=True)
        
        # Check users
        cursor.execute("SELECT username, role, password_hash FROM users")
        users = cursor.fetchall()
        results.append("--- Registered Users ---")
        for user in users:
            results.append(f"User: {user['username']}, Role: {user['role']}, Password: {user['password_hash']}")
            
        conn.close()
    except Exception as e:
        results.append(f"Error: {e}")

    with open("results.txt", "w") as f:
        f.write("\n".join(results))

if __name__ == "__main__":
    verify_users()
