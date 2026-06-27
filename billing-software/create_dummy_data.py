import mysql.connector
from config import Config
from datetime import datetime, timedelta

def normalize_category(cat, name, bc):
    cat = (cat or '').upper()
    name = (name or '').upper()
    bc = (bc or '')
    if 'OILS' in cat: return 'OILS'
    elif 'SPICES' in cat: return 'SPICES'
    elif 'TEA' in cat: return 'TEA/COFFEE'
    elif 'AROM' in cat: return 'AROMATICS'
    elif 'CAND' in cat or 'NATUR' in cat or 'CANDIES' in cat: return 'CANDIES'
    elif 'MRD' in cat or 'CFC' in cat or 'CHOCO' in cat or 'MRD' in name or 'CHOCO' in name or 'CFC' in name:
        if bc.startswith('18') or bc.startswith('8'): return 'CFC'
        else: return 'C-MRD'
    elif 'JELLY' in cat or 'FRUIT' in cat or 'JELLY' in name or 'FRUIT' in name:
        if bc.startswith('195') or bc.startswith('95') or 'VARKEY' in name: return 'VARKEY'
        else: return 'FRUIT JELLY'
    elif 'VARKEY' in cat or 'VARKEY' in name: return 'VARKEY'
    else: return 'OTHERS'

def main():
    print("Connecting to DB...")
    conn = mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB
    )
    cursor = conn.cursor(dictionary=True)
    
    print("Wipe skipped.")
    
    categories_to_find = [
        'AROMATICS', 'CFC', 'C-MRD', 'CANDIES', 'FRUIT JELLY', 
        'OILS', 'OTHERS', 'SPICES', 'TEA/COFFEE', 'VARKEY'
    ]
    
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()
    products.sort(key=lambda x: float(x['price'] or 0), reverse=True)
    
    cat_to_product = {}
    for p in products:
        n_cat = normalize_category(p['category'], p['name'], p['barcode'])
        if n_cat not in cat_to_product:
            cat_to_product[n_cat] = p
            
    for cat in categories_to_find:
        if cat not in cat_to_product:
            dummy_bc = "999" + str(len(cat_to_product))
            cursor.execute("INSERT INTO products (name, barcode, category, price, stock) VALUES (%s, %s, %s, %s, %s)",
                           (f"Dummy {cat}", dummy_bc, cat, 10.0, 100))
            conn.commit()
            cat_to_product[cat] = {
                'name': f"Dummy {cat}",
                'barcode': dummy_bc,
                'category': cat,
                'price': 10.0,
                'stock': 100
            }
            print(f"Created dummy product for {cat}")
            
    today = datetime.now()
    
    # 2 Bills: One Completed ('Paid') and One 'Cancelled'
    bills_to_create = [
        {'invoice': f"INV-{today.strftime('%y%m%d%H%M')}P", 'status': 'Paid'},
        {'invoice': f"INV-{today.strftime('%y%m%d%H%M')}C", 'status': 'Cancelled'}
    ]
    
    for bill_info in bills_to_create:
        date_str = today.strftime('%Y-%m-%d %H:%M:%S')
        total = sum([float(cat_to_product[cat].get('price') or 10.0) for cat in categories_to_find])
        
        cursor.execute(
            "INSERT INTO bills (invoice_no, total_amount, payment_mode, bill_date, status) VALUES (%s, %s, %s, %s, %s)",
            (bill_info['invoice'], total, 'Cash', date_str, bill_info['status'])
        )
        bill_id = cursor.lastrowid
        
        for cat in categories_to_find:
            p = cat_to_product[cat]
            price = float(p.get('price') or 10.0)
            cursor.execute(
                "INSERT INTO bill_items (bill_id, product_name, qty, rate, amount) VALUES (%s, %s, %s, %s, %s)",
                (bill_id, p['name'], 1, price, price)
            )
    
    conn.commit()
    conn.close()
    print("One active bill and one cancelled bill generated successfully!")

if __name__ == '__main__':
    main()
