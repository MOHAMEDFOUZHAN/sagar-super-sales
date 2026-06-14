import mysql.connector

conn = mysql.connector.connect(host='127.0.0.1', user='root', password='', database='maple_pro_db')
cursor = conn.cursor()

cursor.execute("UPDATE bills SET created_by = 'counter1' WHERE created_by = 'SYSTEM'")
conn.commit()
print(f'Updated {cursor.rowcount} bills from SYSTEM to counter1')
conn.close()
