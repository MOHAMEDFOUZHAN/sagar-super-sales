import mysql.connector
import datetime
import random
import uuid
import sys
import os

# Set up paths to import config
script_dir = os.path.dirname(os.path.abspath(__file__))
billing_software_path = os.path.normpath(os.path.join(script_dir, 'billing-software'))
if os.path.exists(billing_software_path):
    sys.path.insert(0, billing_software_path)

try:
    from config import Config
except (ImportError, ModuleNotFoundError):
    class Config:
        MYSQL_HOST = '127.0.0.1'; MYSQL_USER = 'root'; MYSQL_PASSWORD = ''; MYSQL_DB = 'maple_pro_db'

DATE_TO_GENERATE = datetime.date(2026, 4, 11)
TARGET_TOTAL_SALES = 40000.0
TARGET_PER_COUNTER = TARGET_TOTAL_SALES / 4

def calculate_tsc(total):
    if total >= 10000: return 3.0
    if total >= 7000: return 2.5
    if total >= 5000: return 2.0
    if total >= 2500: return 1.5
    if total >= 1000: return 1.0
    return 0.0

def run_generation():
    print(f"--- Corrected Test: Total Rs {TARGET_TOTAL_SALES} for {DATE_TO_GENERATE} ---")
    
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST, user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD, database=Config.MYSQL_DB
        )
        cursor = conn.cursor(dictionary=True)
    except Exception as e:
        print(f"Error connecting: {e}")
        return

    # 1. Fetch products
    cursor.execute("SELECT barcode, name, price, bizz FROM products")
    all_products = cursor.fetchall()
    chocolate_keywords = ['CHOCO', 'MRD', 'CFC', 'JELLY', 'VARKEY']
    choc_prods = [p for p in all_products if any(k in (p['name'] or '').upper() for k in chocolate_keywords)]
    gen_prods = [p for p in all_products if p not in choc_prods]

    # 2. Cleanup MUST happen first
    print("Cleanup: Removing high-volume records...")
    cursor.execute("DELETE FROM `bill_items` WHERE `bill_id` IN (SELECT `id` FROM `bills` WHERE DATE(`bill_date`) = %s)", (DATE_TO_GENERATE,))
    cursor.execute("DELETE FROM `bills` WHERE DATE(`bill_date`) = %s", (DATE_TO_GENERATE,))
    cursor.execute("DELETE FROM `bill_sequences` WHERE `seq_date` = %s", (DATE_TO_GENERATE,))
    cursor.execute("INSERT INTO `bill_sequences` (`seq_date`, `last_value`) VALUES (%s, %s)", (DATE_TO_GENERATE, 0))
    conn.commit()

    counters = [
        {'name': 'counter1', 'prods': gen_prods},
        {'name': 'counter2', 'prods': gen_prods},
        {'name': 'counter3', 'prods': choc_prods},
        {'name': 'counter4', 'prods': choc_prods}
    ]
    
    invoice_num = 1
    for c_info in counters:
        user = c_info['name']
        available_prods = c_info['prods']
        current_counter_sales = 0
        
        print(f"Generating ~Rs {TARGET_PER_COUNTER} for {user}...")
        
        while current_counter_sales < TARGET_PER_COUNTER:
            # Create a bill
            invoice_no = f"{DATE_TO_GENERATE.strftime('%Y%m%d')}-{invoice_num:05d}"
            invoice_num += 1
            bill_time = datetime.datetime.combine(DATE_TO_GENERATE, datetime.time(random.randint(9, 20), random.randint(0, 59), random.randint(0, 59)))
            pay_mode = random.choice(['CASH', 'CARD', 'UPI'])
            
            # Select random products
            num_items = random.randint(1, 3)
            selected = random.sample(available_prods, min(num_items, len(available_prods)))
            
            bill_subtotal = 0
            items_for_bill = []
            for p in selected:
                price = float(p['price'] or 0)
                if price <= 0: continue
                
                # Manage qty to reach target
                remaining = TARGET_PER_COUNTER - current_counter_sales
                max_qty = int(remaining / price) + 1
                qty = random.randint(1, min(5, max_qty))
                
                amt = round(qty * price, 2)
                bz_p = float(p['bizz'] or 0); bz_a = round((amt * bz_p) / 100, 2)
                items_for_bill.append((p['barcode'], p['name'], qty, price, amt, bz_p, bz_a))
                bill_subtotal += amt
            
            if bill_subtotal <= 0: break
            
            tsc_p = calculate_tsc(bill_subtotal)
            tsc_a = round((bill_subtotal * tsc_p) / 100, 2)
            
            cursor.execute("INSERT INTO bills (invoice_no, client_request_id, bill_date, total_amount, payment_mode, tsc_percent, tsc_amount, status, created_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                           (invoice_no, str(uuid.uuid4()), bill_time, bill_subtotal, pay_mode, tsc_p, tsc_a, 'PAID', user))
            bill_id = cursor.lastrowid
            
            for itm in items_for_bill:
                cursor.execute("INSERT INTO bill_items (bill_id, product_code, product_name, qty, rate, amount, bizz_percent, bizz_amount) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                               (bill_id, *itm))
            
            current_counter_sales += bill_subtotal
            
        conn.commit()

    cursor.execute("UPDATE `bill_sequences` SET `last_value` = %s WHERE `seq_date` = %s", (invoice_num - 1, DATE_TO_GENERATE))
    conn.commit()
    conn.close()
    print(f"\nSUCCESS: Grand Total for the day is now approximately Rs 40,000.")

if __name__ == "__main__":
    run_generation()
