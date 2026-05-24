import sys
import datetime
from app import get_db_connection

def test_check():
    report_date = datetime.date.today().isoformat()
    print("Checking DB records for date:", report_date)
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to MySQL database")
        return
    
    cursor = conn.cursor(dictionary=True)
    
    # 1. Fetch cash balance record
    cursor.execute("SELECT * FROM cash_balance WHERE balance_date = %s", (report_date,))
    balance = cursor.fetchone()
    print("\n--- CASH BALANCE RECORD ---")
    if balance:
        print(f"ID: {balance['id']}")
        print(f"Date: {balance['balance_date']}")
        print(f"Opening Balance: {balance['opening_balance']}")
        print(f"Closing Balance (Expected): {balance['closing_balance']}")
        print(f"Actual Closing (Counted): {balance['actual_closing']}")
        print(f"Difference: {balance['difference']}")
        print(f"Status: {balance['status']}")
        
        # 2. Fetch denominations
        cursor.execute("SELECT * FROM denominations WHERE balance_id = %s", (balance['id'],))
        denoms = cursor.fetchall()
        print("\n--- DENOMINATIONS ---")
        for d in denoms:
            print(f"Note Value: {d['note_value']} x Count: {d['count']} = {d['note_value'] * d['count']}")
    else:
        print("No cash balance record found for today!")
        
    # 3. Fetch expenses
    cursor.execute("SELECT * FROM expenses WHERE DATE(expense_date) = %s", (report_date,))
    exps = cursor.fetchall()
    print("\n--- TODAY'S EXPENSES ---")
    total_exp = 0
    for e in exps:
        print(f"Category: {e['category']}, Group: {e['expense_group']}, Amount: {e['amount']}")
        total_exp += e['amount']
    print("Total Expenses:", total_exp)
    
    conn.close()

if __name__ == '__main__':
    test_check()
