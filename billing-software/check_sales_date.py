
import mysql.connector
import datetime

def check_sales(target_date_str):
    try:
        conn = mysql.connector.connect(
            host='127.0.0.1',
            user='root',
            password='',
            database='maple_pro_db'
        )
        cursor = conn.cursor(dictionary=True)
        
        # Check bills for the specific date
        query = "SELECT id, invoice_no, total_amount, status, bill_date, discount, tsc_amount FROM bills WHERE DATE(bill_date) = %s"
        cursor.execute(query, (target_date_str,))
        bills = cursor.fetchall()
        
        print(f"--- Deep Audit for {target_date_str} ---")
        if not bills:
            print("No bills found for this date.")
            return
            
        total_bills_sum = 0
        total_items_sum = 0
        
        print(f"{'Inv No':<10} | {'Bill Total':<12} | {'Item Sum':<12} | {'Disc':<8} | {'TSC':<8} | {'Calc Net':<12} | {'Status'}")
        print("-" * 90)
        
        for b in bills:
            bill_id = b['id']
            bill_total = float(b['total_amount'] or 0)
            discount = float(b['discount'] or 0)
            tsc = float(b['tsc_amount'] or 0)
            
            # Fetch items for this bill
            cursor.execute("SELECT SUM(amount) as item_sum FROM bill_items WHERE bill_id = %s", (bill_id,))
            item_res = cursor.fetchone()
            item_sum = float(item_res['item_sum'] or 0)
            
            # Calculated Net = Item Sum - Discount + TSC
            calc_net = round(item_sum - discount + tsc, 2)
            
            status_mark = "OK" if abs(calc_net - bill_total) < 0.01 else "MISMATCH"
            
            if b['status'] != 'Cancelled':
                total_bills_sum += bill_total
                total_items_sum += calc_net
            
            print(f"{b['invoice_no']:<10} | {bill_total:<12.2f} | {item_sum:<12.2f} | {discount:<8.2f} | {tsc:<8.2f} | {calc_net:<12.2f} | {status_mark} ({b['status']})")
            
        print("-" * 90)
        print(f"Total Sales from Bills Table: {total_bills_sum:.2f}")
        print(f"Total Sales from Items (Recalc): {total_items_sum:.2f}")
        
        if abs(total_bills_sum - total_items_sum) > 0.01:
            print(f"\nWARNING: Found a discrepancy of {abs(total_bills_sum - total_items_sum):.2f}!")
        else:
            print("\nSUCCESS: All bills match their item totals.")
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_sales("2026-06-13")
