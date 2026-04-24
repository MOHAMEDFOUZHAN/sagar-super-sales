import mysql.connector
import os

try:
    conn = mysql.connector.connect(
        host='127.0.0.1',
        user='root',
        password='',
        database='sagar_super_db'
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT username, role, password_hash FROM users")
    users = cursor.fetchall()
    with open("db_status_report.txt", "w") as f:
        f.write("CONNECTION SUCCESSFUL\n")
        for u in users:
            f.write(f"User: {u['username']}, Role: {u['role']}, Pass: {u['password_hash']}\n")
    conn.close()
except Exception as e:
    with open("db_status_report.txt", "w") as f:
        f.write(f"CONNECTION FAILED: {str(e)}\n")


