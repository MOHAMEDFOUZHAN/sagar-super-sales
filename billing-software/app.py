from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, Response
import mysql.connector
from mysql.connector import pooling
import datetime
import sys
import os
import queue
import time
from config import Config
from backend.sales import create_bill

# Global queue for real-time notifications
# In a multi-worker environment like Waitress, we use a simple list of queues
# to ensure all connected clients receive the update.
class MessageAnnouncer:
    def __init__(self):
        self.listeners = []

    def listen(self):
        q = queue.Queue(maxsize=5)
        self.listeners.append(q)
        return q

    def announce(self, msg):
        for i in reversed(range(len(self.listeners))):
            try:
                self.listeners[i].put_nowait(msg)
            except queue.Full:
                del self.listeners[i]

announcer = MessageAnnouncer()

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# --- Automatic Documents Folder setup ---
DOCUMENTS_FOLDER = os.path.join(os.path.expanduser("~"), "Documents", "MapleSoftware")
if not os.path.exists(DOCUMENTS_FOLDER):
    os.makedirs(DOCUMENTS_FOLDER)

app = Flask(__name__, 
            template_folder=resource_path('frontend'), 
            static_folder=resource_path('frontend'), 
            static_url_path='')
app.secret_key = Config.SECRET_KEY

def format_sse(data: str, event=None) -> str:
    msg = f'data: {data}\n\n'
    if event:
        msg = f'event: {event}\n{msg}'
    return msg

@app.route('/api/realtime/stream')
def realtime_stream():
    def stream():
        messages = announcer.listen()
        while True:
            msg = messages.get() # blocks until a new message arrives
            yield format_sse(data=msg, event='billing_update')
    return Response(stream(), mimetype='text/event-stream')

db_pool = None


def log_error(msg):
    try:
        log_path = os.path.join(getattr(Config, 'ACTIVE_CONFIG_PATH', '.').replace('config.json', ''), 'connection_debug.txt')
        with open(log_path, 'a') as f:
            f.write(f"[{datetime.datetime.now()}] {msg}\n")
    except: pass

def get_db_pool():
    global db_pool
    if db_pool is None:
        try:
            db_pool = pooling.MySQLConnectionPool(
                pool_name=Config.MYSQL_POOL_NAME,
                pool_size=Config.MYSQL_POOL_SIZE,
                host=Config.MYSQL_HOST,
                port=Config.MYSQL_PORT,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DB,
                autocommit=Config.MYSQL_AUTOCOMMIT,
            )
        except Exception as e:
            err_msg = f"CRITICAL Pool Error: {e}"
            print(err_msg)
            log_error(err_msg)
            db_pool = None
    return db_pool

def get_db_connection():
    try:
        pool = get_db_pool()
        if not pool: return None
        conn = pool.get_connection()
        conn.autocommit = Config.MYSQL_AUTOCOMMIT
        cursor = conn.cursor()
        cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
        cursor.close()
        return conn
    except Exception as err:
        err_msg = f"Connection Error: {err}"
        print(err_msg)
        log_error(err_msg)
        return None

@app.route('/api/config/server-ip', methods=['GET', 'POST'])
def manage_server_ip():
    if request.method == 'GET':
        return jsonify({
            'current_ip': Config.MYSQL_HOST,
            'active_config': getattr(Config, 'ACTIVE_CONFIG_PATH', 'Not Found')
        })
    
    data = request.json
    new_ip = data.get('ip', '127.0.0.1').strip()
    
    try:
        # 1. Update Class Memory
        Config.MYSQL_HOST = new_ip
        
        # 2. Update config.json file
        config_path = getattr(Config, 'ACTIVE_CONFIG_PATH', None)
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            config_data['MYSQL_HOST'] = new_ip
            
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=4)
        
        # 3. Reset DB Pool to force reconnect to new IP
        global db_pool
        db_pool = None 
        
        return jsonify({'status': 'success', 'message': f'Server IP updated to {new_ip}. Please restart if connection fails.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/config/fix-db-permissions', methods=['POST'])
def fix_db_permissions_route():
    """Trigger the remote access fix logic on the Server PC"""
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host='127.0.0.1',
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            port=Config.MYSQL_PORT
        )
        cursor = conn.cursor()
        hosts = ['%', '127.0.0.1', 'localhost']
        for host in hosts:
            try:
                cursor.execute(f"CREATE USER IF NOT EXISTS 'root'@'{host}' IDENTIFIED BY ''")
                cursor.execute(f"GRANT ALL PRIVILEGES ON *.* TO 'root'@'{host}' WITH GRANT OPTION")
            except: pass
        cursor.execute("FLUSH PRIVILEGES")
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': 'Remote access enabled on this Server PC.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def log_audit(cursor, action, table_name, record_id, old_val=None, new_val=None):
    try:
        cursor.execute("""
            INSERT INTO audit_logs (user_id, action, table_name, record_id, old_value, new_value)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (session.get('username', 'SYSTEM'), action, table_name, record_id, str(old_val), str(new_val)))
    except Exception as e:
        print(f"Audit Log Error: {e}")

def check_and_init_db():
    print("Initializing Database...")
    try:
        # 1. Connect to MySQL Server
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD
        )
        cursor = conn.cursor()
        
        # 2. Create Database if missing
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.MYSQL_DB}")
        cursor.execute(f"USE {Config.MYSQL_DB}")
        
        # 3. Define all tables and their SQL
        tables = {
            "users": """CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role ENUM('admin', 'sales', 'account') DEFAULT 'sales',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            "products": """CREATE TABLE IF NOT EXISTS products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                barcode VARCHAR(50) UNIQUE,
                name VARCHAR(100) NOT NULL,
                category VARCHAR(50),
                price DECIMAL(10, 2) NOT NULL,
                current_stock INT DEFAULT 0,
                unit VARCHAR(20) DEFAULT 'PCS',
                bizz DECIMAL(10, 2) DEFAULT 0.00,
                min_threshold INT DEFAULT 25,
                expiry_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX (barcode), INDEX (name)
            )""",
            "categories": "CREATE TABLE IF NOT EXISTS categories (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(100) NOT NULL UNIQUE)",
            "bills": """CREATE TABLE IF NOT EXISTS bills (
                id INT AUTO_INCREMENT PRIMARY KEY,
                invoice_no VARCHAR(20) UNIQUE,
                client_request_id VARCHAR(64) UNIQUE,
                bill_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_amount DECIMAL(10, 2) NOT NULL,
                payment_mode VARCHAR(20),
                status VARCHAR(20) DEFAULT 'Paid',
                tsc_percent DECIMAL(5, 2) DEFAULT 0.00,
                tsc_amount DECIMAL(10, 2) DEFAULT 0.00,
                discount DECIMAL(10, 2) DEFAULT 0.00,
                source_bill_id INT,
                prev_total DECIMAL(10, 2) DEFAULT 0.00,
                balance DECIMAL(10, 2) DEFAULT 0.00,
                created_by VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX (bill_date), INDEX (status)
            )""",
            "bill_items": """CREATE TABLE IF NOT EXISTS bill_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                bill_id INT,
                product_code VARCHAR(50),
                product_name VARCHAR(100),
                qty DECIMAL(10, 2),
                rate DECIMAL(10, 2),
                amount DECIMAL(10, 2),
                bizz_percent DECIMAL(5, 2),
                bizz_amount DECIMAL(10, 2),
                FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
            )""",
            "bill_sequences": """CREATE TABLE IF NOT EXISTS bill_sequences (
                seq_date DATE PRIMARY KEY,
                last_value INT NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )""",
            "stock_movements": """CREATE TABLE IF NOT EXISTS stock_movements (
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_id INT NOT NULL,
                bill_id INT,
                movement_type VARCHAR(30) NOT NULL,
                qty_change DECIMAL(10, 2) NOT NULL,
                stock_before DECIMAL(10, 2) NOT NULL,
                stock_after DECIMAL(10, 2) NOT NULL,
                created_by VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id),
                FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE SET NULL
            )""",
            "returns_log": """CREATE TABLE IF NOT EXISTS returns_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                bill_id INT,
                product_name VARCHAR(100),
                qty DECIMAL(10, 2),
                amount DECIMAL(10, 2),
                reason TEXT,
                product_code VARCHAR(50),
                status VARCHAR(50),
                action VARCHAR(50),
                created_by VARCHAR(50),
                return_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
            )""",
            "expenses": """CREATE TABLE IF NOT EXISTS expenses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                expense_date DATE,
                category VARCHAR(50),
                amount DECIMAL(10, 2),
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            "audit_logs": """CREATE TABLE IF NOT EXISTS audit_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id VARCHAR(50),
                action VARCHAR(255),
                table_name VARCHAR(50),
                record_id INT,
                old_value TEXT,
                new_value TEXT,
                action_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            "cash_balance": """CREATE TABLE IF NOT EXISTS cash_balance (
                id INT AUTO_INCREMENT PRIMARY KEY,
                balance_date DATE UNIQUE,
                opening_balance DECIMAL(10, 2),
                closing_balance DECIMAL(10, 2),
                actual_closing DECIMAL(10, 2),
                difference DECIMAL(10, 2),
                status VARCHAR(20) DEFAULT 'CLOSED'
            )""",
            "denominations": """CREATE TABLE IF NOT EXISTS denominations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                balance_id INT,
                note_value INT,
                count INT,
                FOREIGN KEY (balance_id) REFERENCES cash_balance(id) ON DELETE CASCADE
            )""",
            "account_entries": """CREATE TABLE IF NOT EXISTS account_entries (
                id INT AUTO_INCREMENT PRIMARY KEY,
                entry_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                major_type ENUM('Asset', 'Liability', 'Equity', 'Revenue', 'Direct Expense', 'Operating Expense') NOT NULL,
                sub_type VARCHAR(100) NOT NULL,
                description TEXT,
                amount DECIMAL(15, 2) NOT NULL,
                payment_type ENUM('Cash', 'UPI', 'Bank', 'Other') DEFAULT 'Cash',
                created_by INT,
                INDEX (entry_date),
                INDEX (major_type)
            )"""
        }

        # 4. Create each table if it doesn't exist
        for table_name, sql in tables.items():
            cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
            if not cursor.fetchone():
                print(f"Table '{table_name}' missing. Creating...")
                cursor.execute(sql)

        # 5. Ensure default users exist
        default_users = [
            ('admin', 'admin123', 'admin'),
            ('counter', '123', 'sales'),
            ('counter1', '123', 'sales'),
            ('counter2', '123', 'sales'),
            ('counter3', '123', 'sales'),
            ('counter4', '123', 'sales'),
            ('accountant', 'account123', 'account')
        ]
        cursor.executemany("INSERT IGNORE INTO users (username, password_hash, role) VALUES (%s, %s, %s)", default_users)
        
        conn.commit()
        conn.close()
        print("Database initialization check complete.")
    except Exception as e:
        err_msg = f"CRITICAL: Database Initialization Failed. Error: {e}"
        print(err_msg)
        log_error(err_msg)


def process_seed_item(cursor, code, name, rate, bizz, category):
    try:
        if not code or not name: return
        code = "1" + str(code).strip()
        name = name.strip()
        def clean_val(v):
            if not v: return 0.0
            try: return float(str(v).replace(',', '').strip())
            except: return 0.0
        price = clean_val(rate)
        bizz_val = clean_val(bizz)
        cursor.execute("""
            INSERT IGNORE INTO products (barcode, name, category, price, bizz, current_stock, unit) 
            VALUES (%s, %s, %s, %s, %s, 100, 'PCS')
        """, (code, name, category, price, bizz_val))
    except Exception as e:
        print(f"Skipping row {name}: {e}")
        # Note: If MySQL server isn't running (Laragon not started), this will fail.

# Check database before first request
with app.app_context():
    check_and_init_db()

@app.route('/')
def index():

    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
                user = cursor.fetchone()
            except Exception as e:
                flash(f'Database query error: {e}', 'error')
                user = None
            finally:
                if conn: conn.close()

            if user and user['password_hash'] == password: 
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                
                if user.get('role') == 'admin':
                    return redirect(url_for('admin_dashboard'))
                elif user.get('role') == 'account':
                    return redirect(url_for('account_dashboard'))
                return redirect(url_for('sales_dashboard'))
            else:
                flash('Invalid credentials. Please try again.', 'error')
        else:
            # Check if there is a specific error stored
            db_err = session.get('last_db_error', 'Please check if MySQL is running.')
            flash(f'Database connection failed: {db_err}', 'error')
            session.pop('last_db_error', None)
            
    return render_template('login.html', current_host=Config.MYSQL_HOST)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    return render_template('admin/dashboard.html')

@app.route('/account/dashboard')
def account_dashboard():
    return render_template('account/dashboard.html')

@app.route('/account/entry')
def account_entry():
    return render_template('account/entry.html')

@app.route('/api/account/save-entry', methods=['POST'])
def api_account_save_entry():
    data = request.json
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO account_entries (major_type, sub_type, description, amount, payment_type)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            data['major_type'],
            data['sub_type'],
            data['description'],
            data['amount'],
            data['payment_type']
        ))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/admin/intelligence/stock')
def admin_intelligence_stock():
    return render_template('admin/intelligence/stock_intel.html')

@app.route('/admin/analytics')
def admin_analytics():
    return render_template('admin/analytics.html')

@app.route('/admin/masters/products')
def admin_products():
    return render_template('admin/masters/products.html')

@app.route('/admin/masters/users')
def admin_users():
    return render_template('admin/masters/users.html')

@app.route('/api/admin/users', methods=['GET', 'POST'])
def manage_users():
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'DB Fail'}), 500
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'GET':
        cursor.execute("SELECT id, username, role FROM users")
        users = cursor.fetchall()
        conn.close()
        return jsonify(users)
        
    elif request.method == 'POST':
        data = request.json
        uid = data.get('id')
        username = data.get('username')
        password = data.get('password')
        role = data.get('role', 'sales')
        
        try:
            if uid:
                if password:
                    cursor.execute("UPDATE users SET username=%s, password_hash=%s, role=%s WHERE id=%s", (username, password, role, uid))
                else:
                    cursor.execute("UPDATE users SET username=%s, role=%s WHERE id=%s", (username, role, uid))
            else:
                cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)", (username, password, role))
            
            conn.commit()
            conn.close()
            return jsonify({'status': 'success'})
        except Exception as e:
            if conn: conn.rollback(); conn.close()
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/users/<int:uid>', methods=['DELETE'])
def delete_user(uid):
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'DB Fail'}), 500
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE id = %s", (uid,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success'})
    except Exception as e:
        if conn: conn.rollback(); conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/admin/masters/categories')
def admin_categories():
    return render_template('admin/masters/categories.html')

@app.route('/admin/stock/manage')
def admin_stock_manage():
    return render_template('admin/stock/stock_manage.html')

@app.route('/admin/stock/transfer')
def admin_stock_transfer():
    return render_template('admin/stock/stock_transfer.html')

@app.route('/admin/reports/billwise-sales')
def admin_reports_billwise_sales():
    return render_template('admin/reports/billwise_sales.html')

@app.route('/admin/reports/sales-report')
def admin_reports_sales_report():
    return render_template('admin/reports/sales_report.html')

@app.route('/admin/reports/daily-sales')
def admin_reports_daily_sales():
    return render_template('admin/reports/daily_sales.html')

@app.route('/admin/reports/detail-sales')
def admin_reports_detail_sales():
    return render_template('admin/reports/detail_sales.html')

@app.route('/admin/reports/total-sales')
def admin_reports_total_sales():
    return render_template('admin/reports/total_sales.html')

@app.route('/admin/reports/daily-stock')
def admin_reports_daily_stock():
    return render_template('admin/reports/daily_stock.html')

@app.route('/admin/reports/cancelled-report')
def admin_reports_cancelled_report():
    return render_template('admin/reports/cancelled_report.html')

@app.route('/admin/reports/transfer-report')
def admin_reports_transfer_report():
    return render_template('admin/reports/transfer_report.html')

@app.route('/admin/reports/final-report')
def admin_reports_final_report():
    return render_template('admin/reports/final_report.html')

@app.route('/admin/reports/change-sales')
def admin_reports_change_sales():
    return render_template('admin/reports/change_sales.html')

@app.route('/admin/reports/expenses')
def admin_reports_expenses():
    return render_template('admin/reports/expense_reports.html')

@app.route('/admin/reports/correction')
def admin_reports_correction():
    return render_template('admin/reports/correction_bills.html')

@app.route('/admin/reports/cash')
def admin_reports_cash():
    return render_template('admin/reports/cash_calc.html')

@app.route('/admin/reports/counter-wise')
def admin_reports_counter_wise():
    return render_template('admin/reports/counter_sales.html')

@app.route('/admin/returns')
def admin_returns():
    return render_template('admin/returns.html')

@app.route('/api/reports/sales-changes')
def get_sales_changes_report():
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    conn = get_db_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    
    try:
        # We query the returns_log which tracks EVERY return/void action.
        # We JOIN with bills as 'b' for metadata.
        # We also check if this void was part of an exchange (reprocess=1).
        query = """
            SELECT 
                rl.*, 
                b.doc_id as original_doc_id,
                b.payment_mode,
                (SELECT id FROM bills WHERE source_bill_id = rl.bill_id LIMIT 1) as new_bill_id
            FROM returns_log rl
            LEFT JOIN bills b ON rl.bill_id = b.id
            WHERE DATE(rl.return_date) >= %s AND DATE(rl.return_date) <= %s
            ORDER BY rl.return_date DESC
        """
        cursor.execute(query, (start_date, end_date))
        logs = cursor.fetchall()
        
        results = []
        for log in logs:
            # Type classification
            status = log['status'] # 'PARTIAL_RETURN' or 'BILL_CANCELLATION'
            new_id = log.get('new_bill_id')
            
            type_label = status
            if new_id: type_label = 'EXCHANGE'
            elif status == 'BILL_CANCELLATION': type_label = 'FULL VOID'
            elif status == 'PARTIAL_RETURN': type_label = 'RETURN'

            results.append({
                'date': log['return_date'].strftime('%Y-%m-%dT%H:%M:%S') if log['return_date'] else None,
                'type': type_label,
                'bill_id': log['bill_id'],
                'doc_id': f"MP-{log['bill_id']:05d}",
                'original_doc': f"MP-{log['bill_id']:05d}",
                'new_doc': f"MP-{new_id:05d}" if new_id else None,
                'product': log['product_name'],
                'qty': float(log['qty'] or 0),
                'amount': float(log['amount'] or 0),
                'reason': log['reason'],
                'action': log['action'], # 'restock' or 'scrap'
                'created_by': log.get('created_by', 'SYSTEM')
            })
            
        return jsonify(results)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/reports/sales-detailed')
def get_detailed_sales_report():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT 
                b.bill_date, b.id as bill_id, b.status as bill_status, b.payment_mode,
                b.total_amount as bill_total, b.tsc_percent, b.tsc_amount,
                bi.product_name, bi.qty, bi.amount, bi.rate, bi.bizz_percent, bi.bizz_amount,
                p.category, p.barcode
            FROM bill_items bi
            JOIN bills b ON bi.bill_id = b.id
            LEFT JOIN products p ON bi.product_name = p.name
            ORDER BY b.bill_date DESC
        """
        cursor.execute(query)
        data = cursor.fetchall()
        conn.close()
        
        for row in data:
            row['amount'] = float(row['amount'] or 0)
            row['rate'] = float(row['rate'] or 0)
            row['bizz_percent'] = float(row.get('bizz_percent') or 0)
            row['bizz_amount'] = float(row.get('bizz_amount') or 0)
            row['bill_total'] = float(row.get('bill_total') or 0)
            row['tsc_percent'] = float(row.get('tsc_percent') or 0)
            row['tsc_amount'] = float(row.get('tsc_amount') or 0)
            if not row['category']: row['category'] = 'Uncategorized'
            if isinstance(row.get('bill_date'), (datetime.datetime, datetime.date)):
                row['bill_date'] = row['bill_date'].isoformat()
            
        return jsonify(data)
    return jsonify([])

@app.route('/api/reports/master')
def get_master_report():
    conn = get_db_connection()
    if not conn: return jsonify([])
    
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            b.bill_date as date, 
            CONCAT('INV-', LPAD(b.id, 5, '0')) as id,
            'SALE' as type,
            bi.product_name as detail,
            bi.qty,
            bi.rate,
            bi.amount,
            bi.bizz_amount,
            p.category,
            b.payment_mode as mode,
            b.status
        FROM bill_items bi
        JOIN bills b ON bi.bill_id = b.id
        LEFT JOIN products p ON bi.product_name = p.name
        ORDER BY b.bill_date DESC
    """)
    sales = cursor.fetchall()
    
    cursor.execute("""
        SELECT 
            expense_date as date,
            CONCAT('EXP-', LPAD(id, 5, '0')) as id,
            'EXPENSE' as type,
            category as detail,
            1.0 as qty,
            amount as rate,
            amount,
            0.0 as bizz_amount,
            'Expense' as category,
            'Cash' as mode,
            'Paid' as status
        FROM expenses
        ORDER BY expense_date DESC
    """)
    expenses = cursor.fetchall()
    
    master = sales + expenses
    master.sort(key=lambda x: x['date'], reverse=True)
    
    for item in master:
        item['amount'] = float(item['amount'] or 0)
        item['rate'] = float(item['rate'] or 0)
        item['qty'] = float(item['qty'] or 0)
        item['bizz_amount'] = float(item.get('bizz_amount') or 0)
        if not item.get('category'): item['category'] = 'General'
        if isinstance(item['date'], (datetime.datetime, datetime.date)):
            item['date'] = item['date'].isoformat()

    conn.close()
    return jsonify(master)

@app.route('/api/reports/daily-range', methods=['GET'])
def get_daily_range_report():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if not start_date_str or not end_date_str:
        return jsonify({'error': 'Start and end dates required'}), 400
        
    start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    conn = get_db_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    
    results = []
    current_date = start_date
    while current_date <= end_date:
        d_str = current_date.isoformat()
        
        # Sales Summary for this day
        cursor.execute("""
            SELECT 
                SUM(total_amount) as total_sales,
                SUM(CASE WHEN UPPER(payment_mode) = 'CASH' THEN total_amount ELSE 0 END) as cash,
                SUM(CASE WHEN UPPER(payment_mode) = 'CARD' THEN total_amount ELSE 0 END) as card,
                SUM(CASE WHEN UPPER(payment_mode) = 'UPI' THEN total_amount ELSE 0 END) as upi
            FROM bills 
            WHERE DATE(bill_date) = %s AND status != 'Cancelled'
        """, (d_str,))
        sales = cursor.fetchone()
        for k in sales: sales[k] = float(sales[k] or 0)
        
        # Category Summary for this day
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN UPPER(p.category) LIKE '%OILS%' THEN 'OILS'
                    WHEN UPPER(p.category) LIKE '%SPICES%' THEN 'SPICES'
                    WHEN UPPER(p.category) LIKE '%TEA%' THEN 'TEA'
                    WHEN UPPER(p.category) LIKE '%AROM%' THEN 'AROM'
                    WHEN UPPER(p.category) LIKE '%NATUR%' THEN 'NATUR'
                    WHEN UPPER(p.name) LIKE '%MRD%' OR UPPER(p.name) LIKE '%CHOCO%' THEN 'C-MRD'
                    WHEN UPPER(p.name) LIKE '%CFC%' THEN 'C-CFC'
                    WHEN UPPER(p.name) LIKE '%FRUIT JELLY%' OR UPPER(p.name) LIKE '%JELLY%' THEN 'FJ'
                    WHEN UPPER(p.name) LIKE '%VARKEY%' THEN 'VARKEY'
                    ELSE 'OTHERS'
                END as sub_cat,
                SUM(bi.amount) as amt
            FROM bill_items bi
            JOIN bills b ON bi.bill_id = b.id
            LEFT JOIN products p ON bi.product_name = p.name
            WHERE DATE(b.bill_date) = %s AND b.status != 'Cancelled'
            GROUP BY sub_cat
        """, (d_str,))
        cats = cursor.fetchall()
        
        cat_map = {'OILS':0,'SPICES':0,'TEA':0,'AROM':0,'NATUR':0,'OTHERS':0,'C-MRD':0,'C-CFC':0,'FJ':0,'VARKEY':0}
        for c in cats:
            cat_map[c['sub_cat']] = float(c['amt'] or 0)
            
        results.append({
            'date': d_str,
            'sales': sales,
            'categories': cat_map
        })
        current_date += datetime.timedelta(days=1)
        
    conn.close()
    return jsonify(results)

@app.route('/api/reports/closure')
def get_closure_report():
    report_date = request.args.get('date', datetime.date.today().isoformat())
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'DB Fail'})
    cursor = conn.cursor(dictionary=True)

    # User-specific filtering
    user_filter = ""
    query_params = [report_date]
    if session.get('role') == 'sales':
        user_filter = " AND created_by = %s"
        query_params.append(session.get('username'))

    try:
        # 1. Sales Summary
        cursor.execute(f"""
            SELECT 
                COUNT(*) as bill_count,
                SUM(total_amount) as total_sales,
                SUM(CASE WHEN UPPER(payment_mode) = 'CASH' THEN total_amount ELSE 0 END) as cash_sales,
                SUM(CASE WHEN UPPER(payment_mode) = 'CARD' THEN total_amount ELSE 0 END) as card_sales,
                SUM(CASE WHEN UPPER(payment_mode) = 'UPI' THEN total_amount ELSE 0 END) as upi_sales,
                SUM(CASE WHEN UPPER(payment_mode) = 'CREDIT' THEN total_amount ELSE 0 END) as credit_sales
            FROM bills 
            WHERE DATE(bill_date) = %s AND status != 'Cancelled'{user_filter}
        """, tuple(query_params))
        sales = cursor.fetchone()
        for k in sales: sales[k] = float(sales[k] or 0)
        sales['avg_bill'] = sales['total_sales'] / sales['bill_count'] if sales['bill_count'] > 0 else 0

        # 2. Bizz Charges (80/20 split)
        cursor.execute(f"""
            SELECT SUM(bi.bizz_amount) as total_bizz
            FROM bill_items bi
            JOIN bills b ON bi.bill_id = b.id
            WHERE DATE(b.bill_date) = %s AND b.status != 'Cancelled'{user_filter}
        """, tuple(query_params))
        total_biz = float(cursor.fetchone()['total_bizz'] or 0)
        biz_80 = total_biz * 0.8
        biz_20 = total_biz * 0.2

        # 3. TSC (80/20 split)
        cursor.execute(f"""
            SELECT SUM(tsc_amount) as total_tsc
            FROM bills
            WHERE DATE(bill_date) = %s AND status != 'Cancelled'{user_filter}
        """, tuple(query_params))
        total_tsc = float(cursor.fetchone()['total_tsc'] or 0)
        tsc_80 = total_tsc * 0.8
        tsc_20 = total_tsc * 0.2

        # 4. Categories
        cursor.execute(f"""
            SELECT p.category, SUM(bi.amount) as category_sales
            FROM bill_items bi
            JOIN bills b ON bi.bill_id = b.id
            LEFT JOIN products p ON bi.product_name = p.name
            WHERE DATE(b.bill_date) = %s AND b.status != 'Cancelled'{user_filter}
            GROUP BY p.category
        """, tuple(query_params))
        categories = cursor.fetchall()
        for c in categories:
            if not c['category']: c['category'] = 'General'
            c['category_sales'] = float(c['category_sales'] or 0)
            c['percent'] = (c['category_sales'] / sales['total_sales'] * 100) if sales['total_sales'] > 0 else 0

        # 5. Expenses
        cursor.execute("SELECT * FROM expenses WHERE DATE(expense_date) = %s", (report_date,))
        expenses_raw = cursor.fetchall()
        office_exps = []
        shop_exps = []
        total_exc = 0
        for e in expenses_raw:
            amt = float(e['amount'] or 0)
            total_exc += amt
            e['amount'] = amt
            if e['expense_group'] == 'OFFICE': office_exps.append(e)
            else: shop_exps.append(e)
        
        # 6. Balance & Denominations
        cursor.execute("SELECT * FROM cash_balance WHERE balance_date = %s", (report_date,))
        balance = cursor.fetchone()
        if not balance:
            balance = {'opening_balance': 2500, 'actual_closing': 0}
        else:
            balance['opening_balance'] = float(balance['opening_balance'])
            balance['actual_closing'] = float(balance['actual_closing'])

        denoms = []
        if 'id' in balance:
            cursor.execute("SELECT * FROM denominations WHERE balance_id = %s", (balance['id'],))
            denoms = cursor.fetchall()

        conn.close()
        return jsonify({
            'meta': {'admin': session.get('username', 'SYSTEM'), 'time': datetime.datetime.now().strftime('%H:%M:%S')},
            'sales': sales,
            'biz_charges': total_biz, 'biz_80': biz_80, 'biz_20': biz_20,
            'tsc_total': total_tsc, 'tsc_80': tsc_80, 'tsc_20': tsc_20,
            'categories': categories,
            'office_expenses': office_exps, 'shop_expenses': shop_exps,
            'total_shop': sum(e['amount'] for e in shop_exps),
            'total_expenses': total_exc,
            'balance': balance,
            'denominations': denoms
        })
    except Exception as e:
        if conn: conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/reports/closure-range', methods=['GET'])
def get_closure_range_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    conn = get_db_connection()
    if not conn: return jsonify({'error': 'DB fail'})
    
    cursor = conn.cursor(dictionary=True)
    
    # Sales Summary
    cursor.execute("""
        SELECT 
            COUNT(*) as bill_count,
            SUM(total_amount) as total_sales,
            SUM(CASE WHEN UPPER(payment_mode) = 'CASH' THEN total_amount ELSE 0 END) as cash_sales,
            SUM(CASE WHEN UPPER(payment_mode) = 'CARD' THEN total_amount ELSE 0 END) as card_sales,
            SUM(CASE WHEN UPPER(payment_mode) = 'UPI' THEN total_amount ELSE 0 END) as upi_sales,
            SUM(CASE WHEN UPPER(payment_mode) = 'CREDIT' THEN total_amount ELSE 0 END) as credit_sales
        FROM bills 
        WHERE DATE(bill_date) BETWEEN %s AND %s AND status != 'Cancelled'
    """, (start_date, end_date))
    sales_summary = cursor.fetchone()
    
    for key in sales_summary:
        if sales_summary[key] is None: sales_summary[key] = 0
        if key != 'bill_count': sales_summary[key] = float(sales_summary[key])

    # Total Bizz
    cursor.execute("""
        SELECT SUM(bizz_amount) as total_bizz
        FROM bill_items bi
        JOIN bills b ON bi.bill_id = b.id
        WHERE DATE(b.bill_date) BETWEEN %s AND %s AND b.status != 'Cancelled'
    """, (start_date, end_date))
    biz_data = cursor.fetchone()
    total_biz = float(biz_data['total_bizz'] or 0)

    # Total Tsc
    cursor.execute("""
        SELECT SUM(tsc_amount) as total_tsc
        FROM bills
        WHERE DATE(bill_date) BETWEEN %s AND %s AND status != 'Cancelled'
    """, (start_date, end_date))
    tsc_data = cursor.fetchone()
    total_tsc = float(tsc_data['total_tsc'] or 0)

    conn.close()
    
    return jsonify({
        'sales': sales_summary,
        'total_bizz': total_biz,
        'total_tsc': total_tsc,
        'biz_charges': total_biz,
        'tsc_total': total_tsc
    })

@app.route('/api/reports/counter-wise', methods=['GET'])
def get_counter_wise_report():
    report_date = request.args.get('date', datetime.date.today().isoformat())
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'DB Fail'})
    
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. High-level Summary per Counter
        cursor.execute("""
            SELECT 
                created_by as counter_name,
                COUNT(*) as bill_count,
                SUM(total_amount) as total_sales,
                SUM(CASE WHEN UPPER(payment_mode) = 'CASH' THEN total_amount ELSE 0 END) as cash_sales,
                SUM(CASE WHEN UPPER(payment_mode) = 'CARD' THEN total_amount ELSE 0 END) as card_sales,
                SUM(CASE WHEN UPPER(payment_mode) = 'UPI' THEN total_amount ELSE 0 END) as upi_sales
            FROM bills
            WHERE DATE(bill_date) = %s AND status != 'Cancelled'
            GROUP BY created_by
            ORDER BY total_sales DESC
        """, (report_date,))
        summary = cursor.fetchall()
        
        for s in summary:
            s['total_sales'] = float(s['total_sales'] or 0)
            s['cash_sales'] = float(s['cash_sales'] or 0)
            s['card_sales'] = float(s['card_sales'] or 0)
            s['upi_sales'] = float(s['upi_sales'] or 0)

        # 2. Detailed Bill List per Counter (grouped for the UI)
        cursor.execute("""
            SELECT id, invoice_no, bill_date, total_amount, payment_mode, created_by
            FROM bills
            WHERE DATE(bill_date) = %s AND status != 'Cancelled'
            ORDER BY created_by, bill_date DESC
        """, (report_date,))
        details = cursor.fetchall()
        
        for d in details:
            d['total_amount'] = float(d['total_amount'] or 0)
            if isinstance(d['bill_date'], (datetime.datetime, datetime.date)):
                d['bill_date'] = d['bill_date'].isoformat()
        
        conn.close()
        return jsonify({
            'date': report_date,
            'summary': summary,
            'details': details
        })
    except Exception as e:
        if conn: conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/reports/closure/save', methods=['POST'])
def save_closure():
    data = request.json
    report_date = data.get('date', datetime.date.today().isoformat())
    opening_bal = float(data.get('opening_balance', 0))
    actual_closing = float(data.get('actual_closing', 0))
    denoms = data.get('denominations', [])
    
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'DB Fail'})
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(total_amount) FROM bills WHERE DATE(bill_date) = %s AND UPPER(payment_mode)='CASH' AND status!='Cancelled'", (report_date,))
        cash_sales = float(cursor.fetchone()[0] or 0)
        
        cursor.execute("SELECT SUM(amount) FROM expenses WHERE DATE(expense_date) = %s", (report_date,))
        total_exp = float(cursor.fetchone()[0] or 0)
        
        cursor.execute("SELECT SUM(bizz_amount) FROM bill_items bi JOIN bills b ON bi.bill_id = b.id WHERE DATE(b.bill_date) = %s AND b.status!='Cancelled'", (report_date,))
        total_biz = float(cursor.fetchone()[0] or 0)
        
        expected_closing = opening_bal + cash_sales - total_exp - total_biz
        diff = actual_closing - expected_closing
        
        cursor.execute("""
            INSERT INTO cash_balance (balance_date, opening_balance, closing_balance, actual_closing, difference, status)
            VALUES (%s, %s, %s, %s, %s, 'CLOSED')
            ON DUPLICATE KEY UPDATE 
            opening_balance=%s, closing_balance=%s, actual_closing=%s, difference=%s, status='CLOSED'
        """, (report_date, opening_bal, expected_closing, actual_closing, diff,
              opening_bal, expected_closing, actual_closing, diff))
        
        balance_id = cursor.lastrowid
        if not balance_id:
             cursor.execute("SELECT id FROM cash_balance WHERE balance_date=%s", (report_date,))
             balance_id = cursor.fetchone()[0]

        cursor.execute("DELETE FROM denominations WHERE balance_id = %s", (balance_id,))
        for d in denoms:
            if int(d['count']) > 0:
                cursor.execute("INSERT INTO denominations (balance_id, note_value, count) VALUES (%s, %s, %s)",
                               (balance_id, d['note_value'], d['count']))
        
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'expected': expected_closing, 'difference': diff})
    except Exception as e:
        if conn: conn.rollback(); conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/save-shift-data', methods=['POST'])
def save_shift_data():
    data = request.json
    report_date = datetime.date.today().isoformat()
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'DB Fail'})
    
    try:
        cursor = conn.cursor()
        
        # 1. Save Expenses
        # First clear today's expenses to avoid duplicates if re-saved
        # Note: If multiple users save at same time, this might be tricky, but usually one counter one saving.
        # Actually, let's filter by created_by if we want to isolate.
        user = session.get('username', 'SYSTEM')
        
        # We don't necessarily want to DELETE all expenses if other counters saved some.
        # But wait, the expenses table doesn't have a 'counter' column in my head.
        # Let's check the schema.
        
        for exp in data.get('expenses', []):
            # Check if exists for this date/category/user (if we add user)
            # For now, let's just INSERT.
            cursor.execute("""
                INSERT INTO expenses (category, amount, expense_date, expense_group)
                VALUES (%s, %s, %s, %s)
            """, (exp['category'], exp['amount'], report_date, exp['expense_group']))

        # 2. Save Balance & Denominations
        opening_bal = float(data.get('opening_balance', 2500))
        
        # We need to calculate expected closing to save it correctly
        cursor.execute("SELECT SUM(total_amount) FROM bills WHERE DATE(bill_date) = %s AND UPPER(payment_mode)='CASH' AND status!='Cancelled'", (report_date,))
        cash_sales = float(cursor.fetchone()[0] or 0)
        
        cursor.execute("SELECT SUM(amount) FROM expenses WHERE DATE(expense_date) = %s", (report_date,))
        total_exp = float(cursor.fetchone()[0] or 0)
        
        cursor.execute("SELECT SUM(bizz_amount) FROM bill_items bi JOIN bills b ON bi.bill_id = b.id WHERE DATE(b.bill_date) = %s AND b.status!='Cancelled'", (report_date,))
        total_biz = float(cursor.fetchone()[0] or 0)
        
        # Denominations Total
        actual_closing = 0
        for d in data.get('denominations', []):
            actual_closing += (int(d['note_value']) * int(d['count']))
            
        expected_closing = opening_bal + cash_sales - total_exp - total_biz
        diff = actual_closing - expected_closing

        cursor.execute("""
            INSERT INTO cash_balance (balance_date, opening_balance, closing_balance, actual_closing, difference, status)
            VALUES (%s, %s, %s, %s, %s, 'OPEN')
            ON DUPLICATE KEY UPDATE 
            opening_balance=%s, closing_balance=%s, actual_closing=%s, difference=%s
        """, (report_date, opening_bal, expected_closing, actual_closing, diff,
              opening_bal, expected_closing, actual_closing, diff))
        
        cursor.execute("SELECT id FROM cash_balance WHERE balance_date=%s", (report_date,))
        balance_id = cursor.fetchone()[0]

        cursor.execute("DELETE FROM denominations WHERE balance_id = %s", (balance_id,))
        for d in data.get('denominations', []):
            if int(d['count']) > 0:
                cursor.execute("INSERT INTO denominations (balance_id, note_value, count) VALUES (%s, %s, %s)",
                               (balance_id, d['note_value'], d['count']))

        conn.commit()
        conn.close()
        return jsonify({'status': 'success'})
    except Exception as e:
        if conn: conn.rollback(); conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/stock/daily-report')
def get_daily_stock_report():
    conn = get_db_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT barcode, name, category, current_stock as stock, unit FROM products ORDER BY category, name")
    data = cursor.fetchall()
    conn.close()
    for row in data:
        row['stock'] = float(row['stock'] or 0)
    return jsonify(data)

@app.route('/api/stock/transfers')
def get_stock_transfers():
    conn = get_db_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT transfer_date, product_barcode, product_name, qty, from_location, to_location FROM stock_transfers ORDER BY transfer_date DESC")
        data = cursor.fetchall()
    except:
        data = []
    conn.close()
    for row in data:
        row['qty'] = float(row['qty'] or 0)
        if isinstance(row.get('transfer_date'), (datetime.datetime, datetime.date)):
            row['transfer_date'] = row['transfer_date'].isoformat()
    return jsonify(data)

@app.route('/api/expenses/all')
def get_all_expenses():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM expenses ORDER BY id DESC LIMIT 500")
        exps = cursor.fetchall()
        conn.close()
        for e in exps:
            e['amount'] = float(e['amount'] or 0)
            if isinstance(e.get('expense_date'), (datetime.datetime, datetime.date)):
                e['expense_date'] = e['expense_date'].isoformat()
            e['date'] = e['expense_date']
        return jsonify(exps)
    return jsonify([])

@app.route('/sales/dashboard')
def sales_dashboard():
    return render_template('sales/dashboard.html')

@app.route('/sales/billing')
def sales_billing():
    return render_template('sales/billing.html')

@app.route('/sales/expenses')
def sales_expenses():
    return render_template('sales/expense.html')

@app.route('/sales/report')
def sales_report():
    return render_template('sales/final_report.html')

@app.route('/api/return-item', methods=['POST'])
def process_return():
    data = request.json
    bill_id = data.get('bill_id')
    reprocess = data.get('reprocess', False)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Fetch current items of the bill
        cursor.execute("SELECT * FROM bill_items WHERE bill_id = %s", (bill_id,))
        original_items = cursor.fetchall()
        
        returned_product = data.get('product')
        returned_qty = float(data.get('qty', 0))
        refund_amount = float(data.get('refund_amount', 0))

        # 1. Auditing the Action
        cursor.execute("SELECT barcode FROM products WHERE name = %s", (returned_product,))
        p_row = cursor.fetchone()
        product_code = p_row['barcode'] if p_row else 'UNKNOWN'
        
        cursor.execute("""
            INSERT INTO returns_log (bill_id, product_name, product_code, qty, amount, reason, status, action, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (bill_id, returned_product, product_code, returned_qty, refund_amount, data.get('reason'), 
              'BILL_EXCHANGE' if reprocess else 'PARTIAL_RETURN', 
              'restock' if data.get('restock', True) else 'scrap', 
              session.get('username', 'SYSTEM')))

        if reprocess:
            # Void OLD bill
            cursor.execute("SELECT total_amount FROM bills WHERE id = %s", (bill_id,))
            old_total = cursor.fetchone()['total_amount']
            cursor.execute("UPDATE bills SET status = 'Cancelled', prev_total = %s, total_amount = 0 WHERE id = %s", (old_total, bill_id))
            
            # Restock ALL original items
            for item in original_items:
                cursor.execute("UPDATE products SET current_stock = current_stock + %s WHERE name = %s", (item['qty'], item['product_name']))
            
            rebill_cart = []
            for item in original_items:
                rem_qty = float(item['qty'])
                if item['product_name'] == returned_product:
                    rem_qty -= returned_qty
                
                if rem_qty > 0:
                    rebill_cart.append({
                        'name': item['product_name'],
                        'qty': rem_qty,
                        'rate': float(item['rate']),
                        'amount': rem_qty * float(item['rate']),
                        'bizz': float(item.get('bizz_percent', 0)),
                        'category': 'General'
                    })
            
            session['reprocess_cart'] = rebill_cart
            session['source_bill_id'] = bill_id
            session.modified = True
            
        else:
            new_bill_total = 0.0
            for item in original_items:
                if item['product_name'] == returned_product:
                    rem_qty = float(item['qty']) - returned_qty
                    if rem_qty > 0:
                        new_amt = rem_qty * float(item['rate'])
                        cursor.execute("UPDATE bill_items SET qty = %s, amount = %s WHERE id = %s", (rem_qty, new_amt, item['id']))
                        new_bill_total += new_amt
                    else:
                        cursor.execute("DELETE FROM bill_items WHERE id = %s", (item['id'],))
                else:
                    new_bill_total += float(item['amount'])
            
            cursor.execute("UPDATE bills SET status = 'RETURNED', total_amount = %s, balance = %s WHERE id = %s", (new_bill_total, new_bill_total, bill_id))
            if data.get('restock', True):
                cursor.execute("UPDATE products SET current_stock = current_stock + %s WHERE name = %s", (returned_qty, returned_product))

        conn.commit()
        conn.close()
        
        # Real-time notification
        announcer.announce("update")
        
        return jsonify({'status': 'success', 'redirect': '/sales/billing' if reprocess else None})
    except Exception as e:
        if 'conn' in locals() and conn: conn.rollback(); conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/reprocess/load')
def load_reprocess_cart():
    cart = session.get('reprocess_cart', [])
    source_id = session.get('source_bill_id')
    session.pop('reprocess_cart', None)
    session.pop('source_bill_id', None)
    return jsonify({'cart': cart, 'source_bill_id': source_id})

@app.route('/api/products')
def search_products():
    q = request.args.get('q', '')
    conn = get_db_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    
    # Counter logic: Counter 3&4 for Chocolate, 1&2 for Balance (Point 2)
    role_filter = ""
    u = session.get('username', '').lower()
    if u in ['counter3', 'counter4']:
        role_filter = " AND (category = 'CHOCOLATE' OR name LIKE '%CHOCO%' OR name LIKE '%MRD%')"
    elif u in ['counter1', 'counter2']:
        role_filter = " AND (category != 'CHOCOLATE' AND name NOT LIKE '%CHOCO%' AND name NOT LIKE '%MRD%')"

    cursor.execute(f"SELECT * FROM products WHERE (name LIKE %s OR barcode = %s){role_filter} LIMIT 20", (f'%{q}%', q))
    products = cursor.fetchall()
    conn.close()
    for p in products:
        p['price'] = float(p['price'])
        if p.get('bizz'): p['bizz'] = float(p['bizz'])
    return jsonify(products)

@app.route('/api/save-bill', methods=['POST'])
def save_bill():
    data = request.json
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        total = float(data['total'])
        discount = float(data.get('discount', 0))
        tsc_percent = 0
        if total >= 10000: tsc_percent = 3.0
        elif total >= 7000: tsc_percent = 2.5
        elif total >= 5000: tsc_percent = 2.0
        elif total >= 2500: tsc_percent = 1.5
        elif total >= 1000: tsc_percent = 1.0
        tsc_amount = (total * tsc_percent) / 100

        status = 'PAID'
        if data.get('is_correction'): status = 'CORRECTION'
            
        # Continuous Global sequence (Does not reset daily)
        global_key = datetime.date(2000, 1, 1)
        today_prefix = datetime.date.today().strftime("%Y%m%d")
        
        cursor.execute("SELECT `last_value` FROM bill_sequences WHERE seq_date = %s FOR UPDATE", (global_key,))
        res = cursor.fetchone()
        
        if res:
            next_val = res[0] + 1
            cursor.execute("UPDATE bill_sequences SET `last_value` = %s WHERE seq_date = %s", (next_val, global_key))
        else:
            # Initialize global sequence if not exists
            cursor.execute("SELECT COUNT(*) FROM bills")
            current_bills = cursor.fetchone()[0]
            next_val = current_bills + 1
            cursor.execute("INSERT INTO bill_sequences (seq_date, `last_value`) VALUES (%s, %s)", (global_key, next_val))
            
        invoice_no = f"MP-{next_val:04d}"

        cursor.execute("""
            INSERT INTO bills (invoice_no, bill_date, total_amount, payment_mode, tsc_percent, tsc_amount, status, source_bill_id, discount, created_by) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (invoice_no, datetime.datetime.now(), total, data['payment_mode'], tsc_percent, tsc_amount, status, data.get('source_bill_id'), discount, session.get('username', 'SYSTEM')))
        bill_id = cursor.lastrowid
        
        for item in data['items']:
            cursor.execute("SELECT current_stock, barcode FROM products WHERE name = %s FOR UPDATE", (item['name'],))
            prod = cursor.fetchone()
            if not prod: raise Exception(f"Product not found: {item['name']}")
                
            available_stock = float(prod[0])
            demanded_qty = float(item['qty'])
            if available_stock < demanded_qty:
                raise Exception(f"Insufficient stock for {item['name']}. Available: {available_stock}")

            bizz_percent = float(item.get('bizz', 0))
            bizz_amt = (float(item['amount']) * bizz_percent) / 100
            cursor.execute("""
                INSERT INTO bill_items (bill_id, product_name, qty, rate, amount, bizz_percent, bizz_amount) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (bill_id, item['name'], item['qty'], item['rate'], item['amount'], bizz_percent, bizz_amt))
            cursor.execute("UPDATE products SET current_stock = current_stock - %s WHERE name = %s", (item['qty'], item['name']))
        
        log_audit(cursor, 'CREATE_BILL', 'bills', bill_id, None, f"Invoice: {invoice_no}, Total: {total}")
        conn.commit(); conn.close()
        
        # Trigger Real-time update
        announcer.announce("update")
        
        return jsonify({'status': 'success', 'bill_id': bill_id})
    except Exception as e:
        if 'conn' in locals() and conn: conn.rollback(); conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    conn = get_db_connection()
    if not conn: return jsonify({'error': 'DB Connection failed'}), 500
    
    cursor = conn.cursor()
    today = datetime.date.today().isoformat()
    
    # User-specific filtering for stats
    user_filter = ""
    query_params = [today]
    if session.get('role') == 'sales':
        user_filter = " AND created_by = %s"
        query_params.append(session.get('username'))
    
    cursor.execute(f"SELECT SUM(total_amount) FROM bills WHERE DATE(bill_date) = %s AND status != 'Cancelled'{user_filter}", tuple(query_params))
    daily_sales = cursor.fetchone()[0] or 0
    
    cursor.execute(f"SELECT COUNT(*) FROM bills WHERE DATE(bill_date) = %s AND status != 'Cancelled'{user_filter}", tuple(query_params))
    bill_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE DATE(expense_date) = %s", (today,))
    expenses = cursor.fetchone()[0] or 0
    
    cursor.execute(f"SELECT payment_mode, SUM(total_amount) FROM bills WHERE DATE(bill_date) = %s AND status != 'Cancelled'{user_filter} GROUP BY payment_mode", tuple(query_params))
    modes = cursor.fetchall()
    
    cash_sales = upi_sales = card_sales = credit_sales = 0
    for mode, amount in modes:
        mode_upper = mode.upper()
        if mode_upper == 'CASH': cash_sales = float(amount)
        elif mode_upper == 'UPI': upi_sales = float(amount)
        elif mode_upper == 'CARD': card_sales = float(amount)
        elif mode_upper == 'CREDIT': credit_sales = float(amount)

    cursor.execute(f"SELECT COUNT(*), SUM(total_amount) FROM bills WHERE DATE(bill_date) = %s AND status = 'Cancelled'{user_filter}", tuple(query_params))
    cancel_data = cursor.fetchone()
    canceled_count = cancel_data[0] or 0
    canceled_amount = cancel_data[1] or 0

    conn.close()
    avg_bill = (float(daily_sales) / bill_count) if bill_count > 0 else 0
    
    return jsonify({
        'daily_sales': float(daily_sales),
        'bill_count': bill_count,
        'expenses': float(expenses),
        'cash_sales': cash_sales,
        'upi_sales': upi_sales,
        'card_sales': card_sales,
        'canceled_bills': canceled_count,
        'canceled_amount': float(canceled_amount),
        'avg_bill_value': float(avg_bill)
    })

@app.route('/api/stats/advanced')
def get_advanced_stats():
    conn = get_db_connection()
    if not conn: return jsonify({'error': 'DB fail'})
    
    cursor = conn.cursor(dictionary=True)
    today = datetime.date.today()
    
    trend = []
    for i in range(6, -1, -1):
        d = today - datetime.timedelta(days=i)
        d_str = d.isoformat()
        cursor.execute("SELECT SUM(total_amount) FROM bills WHERE DATE(bill_date) = %s AND status != 'Cancelled'", (d_str,))
        amt = cursor.fetchone()['SUM(total_amount)'] or 0
        trend.append({'date': d.strftime('%b %d'), 'amount': float(amt)})
    
    last_30 = (today - datetime.timedelta(days=30)).isoformat()
    cursor.execute("""
        SELECT payment_mode, SUM(total_amount) as total 
        FROM bills 
        WHERE DATE(bill_date) >= %s AND status != 'Cancelled'
        GROUP BY payment_mode
    """, (last_30,))
    payments = cursor.fetchall()
    for p in payments: p['total'] = float(p['total'])

    cursor.execute("""
        SELECT bi.product_name, SUM(bi.amount) as revenue
        FROM bill_items bi
        JOIN bills b ON bi.bill_id = b.id
        WHERE b.status != 'Cancelled'
        GROUP BY bi.product_name
        ORDER BY revenue DESC
        LIMIT 5
    """)
    top_products = cursor.fetchall()
    for p in top_products: p['revenue'] = float(p['revenue'])

    conn.close()
    return jsonify({'trend': trend, 'payments': payments, 'top_products': top_products})

@app.route('/api/analytics/deep')
def get_deep_analytics():
    conn = get_db_connection()
    if not conn: return jsonify({'error': 'DB fail'})
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT p.category, SUM(bi.amount) as revenue
        FROM bill_items bi
        JOIN bills b ON bi.bill_id = b.id
        LEFT JOIN products p ON bi.product_name = p.name
        WHERE b.status != 'Cancelled'
        GROUP BY p.category
    """)
    cat_revenue = cursor.fetchall()
    for c in cat_revenue: 
        c['revenue'] = float(c['revenue'])
        if not c['category']: c['category'] = 'Uncategorized'

    cursor.execute("""
        SELECT HOUR(bill_date) as hour, SUM(total_amount) as revenue
        FROM bills
        WHERE status != 'Cancelled'
        GROUP BY hour
        ORDER BY hour
    """)
    hourly_sales = cursor.fetchall()
    
    conn.close()
    return jsonify({
        'category_revenue': cat_revenue,
        'hourly_sales': [{ 'hour': int(h['hour']), 'revenue': float(h['revenue']) } for h in hourly_sales]
    })

@app.route('/api/dashboard/realtime')
def get_dashboard_realtime():
    conn = get_db_connection()
    if not conn: return jsonify({'error': 'DB fail'})
    cursor = conn.cursor(dictionary=True)
    today = datetime.date.today()

    # User-specific filtering
    user_filter = ""
    query_params_today = [today]
    if session.get('role') == 'sales':
        user_filter = " AND created_by = %s"
        query_params_today.append(session.get('username'))

    cursor.execute(f"""
        SELECT HOUR(bill_date) as hour, SUM(total_amount) as revenue
        FROM bills
        WHERE DATE(bill_date) = %s AND status != 'Cancelled'{user_filter}
        GROUP BY hour
        ORDER BY hour
    """, tuple(query_params_today))
    hourly_raw = cursor.fetchall()
    
    hourly_map = {row['hour']: float(row['revenue']) for row in hourly_raw}
    hourly_data = []
    labels = []
    for h in range(9, 22):
        ampm = 'AM' if h < 12 else 'PM'
        display_h = h if h <= 12 else h - 12
        labels.append(f"{display_h}{ampm}")
        hourly_data.append(hourly_map.get(h, 0))

    cursor.execute(f"""
        SELECT payment_mode, SUM(total_amount) as total
        FROM bills
        WHERE DATE(bill_date) = %s AND status != 'Cancelled'{user_filter}
        GROUP BY payment_mode
    """, tuple(query_params_today))
    payment_map = {row['payment_mode']: float(row['total']) for row in cursor.fetchall()}

    cursor.execute(f"""
        SELECT p.category, SUM(bi.amount) as revenue
        FROM bill_items bi
        JOIN bills b ON bi.bill_id = b.id
        LEFT JOIN products p ON bi.product_name = p.name
        WHERE DATE(b.bill_date) = %s AND b.status != 'Cancelled'{user_filter}
        GROUP BY p.category
        ORDER BY revenue DESC
        LIMIT 5
    """, tuple(query_params_today))
    cat_raw = cursor.fetchall()
    categories = [c['category'] if c['category'] else 'General' for c in cat_raw]
    cat_revenues = [float(c['revenue']) for c in cat_raw]

    cursor.execute(f"""
        SELECT bi.product_name, SUM(bi.qty) as qty, SUM(bi.amount) as revenue
        FROM bill_items bi
        JOIN bills b ON bi.bill_id = b.id
        WHERE DATE(b.bill_date) = %s AND b.status != 'Cancelled'{user_filter}
        GROUP BY bi.product_name
        ORDER BY revenue DESC
        LIMIT 5
    """, tuple(query_params_today))
    top_prods = cursor.fetchall()
    for p in top_prods:
        p['qty'] = float(p['qty'])
        p['revenue'] = float(p['revenue'])

    conn.close()
    return jsonify({
        'hourly': {'labels': labels, 'data': hourly_data},
        'payments': payment_map,
        'categories': {'labels': categories, 'data': cat_revenues},
        'top_products': top_prods
    })

@app.route('/api/next-invoice')
def get_next_invoice():
    today_prefix = datetime.datetime.now().strftime("%Y%m%d")
    global_key = datetime.date(2000, 1, 1)
    conn = get_db_connection()
    if not conn: return jsonify({'next_id': f"MP-00000"})
    cursor = conn.cursor()
    cursor.execute("SELECT `last_value` FROM bill_sequences WHERE seq_date = %s", (global_key,))
    res = cursor.fetchone()
    next_val = 1
    if res:
        next_val = res[0] + 1
    else:
        # Fallback to count
        cursor.execute("SELECT COUNT(*) FROM bills")
        next_val = cursor.fetchone()[0] + 1
        
    conn.close()
    return jsonify({'next_id': f"MP-{next_val:04d}"})

@app.route('/api/bills/recent')
def get_recent_bills():
    conn = get_db_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    
    user_filter = ""
    params = []
    if session.get('role') == 'sales':
        user_filter = " WHERE created_by = %s"
        params.append(session.get('username'))
        
    cursor.execute(f"SELECT id, invoice_no, total_amount, bill_date, status FROM bills{user_filter} ORDER BY id DESC LIMIT 50", tuple(params))
    bills = cursor.fetchall()
    conn.close()
    for b in bills:
        b['total_amount'] = float(b['total_amount'])
        if isinstance(b['bill_date'], (datetime.datetime, datetime.date)):
            b['bill_date'] = b['bill_date'].isoformat()
    return jsonify(bills)

@app.route('/api/bills/all')
def get_all_bills_api():
    conn = get_db_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    # Fetching all columns needed by the Bill-wise report
    cursor.execute("SELECT id, invoice_no, total_amount, bill_date, status, discount, prev_total, source_bill_id FROM bills ORDER BY id DESC")
    bills = cursor.fetchall()
    conn.close()
    for b in bills:
        b['total_amount'] = float(b['total_amount'] or 0)
        b['discount'] = float(b.get('discount') or 0)
        b['prev_total'] = float(b.get('prev_total') or 0)
        if isinstance(b['bill_date'], (datetime.datetime, datetime.date)):
            b['bill_date'] = b['bill_date'].isoformat()
    return jsonify(bills)

@app.route('/api/bills/<int:bill_id>/items')
def get_bill_items_api(bill_id):
    conn = get_db_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM bill_items WHERE bill_id = %s", (bill_id,))
    items = cursor.fetchall()
    conn.close()
    for i in items:
        i['qty'] = float(i['qty'])
        i['rate'] = float(i['rate'])
        i['amount'] = float(i['amount'])
    return jsonify(items)

@app.route('/api/bills/void', methods=['POST'])
def void_bill_api():
    data = request.json
    bill_id = data.get('bill_id')
    reason = data.get('reason', 'VOIDED BY USER')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get bill info
        cursor.execute("SELECT invoice_no, total_amount, status FROM bills WHERE id = %s", (bill_id,))
        bill = cursor.fetchone()
        if not bill: throw_error("Bill not found")
        if bill[2] == 'Cancelled': return jsonify({'status': 'error', 'message': 'Already Voided'})
        
        # 1. Update bill status
        cursor.execute("UPDATE bills SET status = 'Cancelled', prev_total = total_amount, total_amount = 0 WHERE id = %s", (bill_id,))
        
        # 2. Restock items
        cursor.execute("SELECT product_name, qty FROM bill_items WHERE bill_id = %s", (bill_id,))
        items = cursor.fetchall()
        for name, qty in items:
            cursor.execute("UPDATE products SET current_stock = current_stock + %s WHERE name = %s", (qty, name))
            
        # 3. Audit log
        log_audit(cursor, 'VOID_BILL', 'bills', bill_id, f"Invoice: {bill[0]}", f"Reason: {reason}")
        
        conn.commit()
        conn.close()
        
        # Real-time trigger
        announcer.announce("update")
        
        return jsonify({'status': 'success'})
    except Exception as e:
        if 'conn' in locals() and conn: conn.rollback(); conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/intelligence/stock-alerts')
def get_stock_alerts():
    conn = get_db_connection()
    if not conn: return jsonify({'error': 'DB fail'})
    cursor = conn.cursor(dictionary=True)
    today = datetime.date.today()
    expiring_soon_threshold = today + datetime.timedelta(days=30)
    
    cursor.execute("""
        SELECT barcode, name, category, current_stock as stock, unit, min_threshold
        FROM products 
        WHERE current_stock <= min_threshold
    """)
    low_stock = cursor.fetchall()

    cursor.execute("""
        SELECT barcode, name, category, expiry_date, current_stock as stock
        FROM products 
        WHERE expiry_date IS NOT NULL AND expiry_date <= %s
        ORDER BY expiry_date ASC
    """, (expiring_soon_threshold.isoformat(),))
    expiring_soon = cursor.fetchall()
    for e in expiring_soon: e['expiry_date'] = e['expiry_date'].isoformat()

    cursor.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN current_stock <= min_threshold THEN 1 ELSE 0 END) as low_count
        FROM products
    """)
    summary = cursor.fetchone()
    
    cursor.execute("""
        SELECT COUNT(DISTINCT bi.product_name) as fast_moving
        FROM bill_items bi
        JOIN bills b ON bi.bill_id = b.id
        WHERE b.bill_date >= DATE_SUB(NOW(), INTERVAL 3 DAY)
          AND b.status != 'Cancelled'
    """)
    fast_count = cursor.fetchone()['fast_moving'] or 0
    conn.close()
    
    total_items = summary['total'] or 1
    health_score = max(0, 100 - (summary['low_count'] / total_items * 100))
    return jsonify({
        'low_stock': low_stock, 'expiring_soon': expiring_soon,
        'health': {'score': round(health_score), 'total_items': total_items, 'fast_moving': fast_count, 'low_count': summary['low_count']}
    })

@app.route('/api/cancel-bill', methods=['POST'])
def cancel_bill():
    data = request.json
    bill_id = data.get('bill_id')
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'DB fail'}), 500
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT status, total_amount FROM bills WHERE id = %s", (bill_id,))
        bill = cursor.fetchone()
        if not bill: raise Exception("Bill not found")
        if bill['status'] == 'Cancelled': return jsonify({'status': 'info', 'message': 'Already cancelled'})

        # 1. Restock items
        cursor.execute("SELECT product_name, qty FROM bill_items WHERE bill_id = %s", (bill_id,))
        items = cursor.fetchall()
        for item in items:
            cursor.execute("UPDATE products SET current_stock = current_stock + %s WHERE name = %s", (item['qty'], item['product_name']))

        # 2. Mark bill as cancelled
        cursor.execute("UPDATE bills SET status = 'Cancelled', total_amount = 0 WHERE id = %s", (bill_id,))
        
        log_audit(cursor, 'CANCEL_BILL', 'bills', bill_id, f"Total: {bill['total_amount']}", "Cancelled")
        conn.commit(); conn.close()
        return jsonify({'status': 'success'})
    except Exception as e:
        if conn: conn.rollback(); conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/inventory/categories', methods=['GET', 'POST', 'DELETE'])
@app.route('/api/inventory/categories/<int:cat_id>', methods=['DELETE'])
def inventory_categories(cat_id=None):
    conn = get_db_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'GET':
        cursor.execute("SELECT * FROM categories ORDER BY name")
        res = cursor.fetchall()
        conn.close()
        return jsonify(res)
        
    elif request.method == 'POST':
        data = request.json
        try:
            cursor.execute("INSERT INTO categories (name) VALUES (%s)", (data['name'],))
            conn.commit(); conn.close()
            return jsonify({'status': 'success'})
        except Exception as e:
            if conn: conn.rollback(); conn.close()
            return jsonify({'status': 'error', 'message': str(e)}), 500
            
    elif request.method == 'DELETE':
        cid = cat_id or request.json.get('id')
        try:
            cursor.execute("DELETE FROM categories WHERE id = %s", (cid,))
            conn.commit(); conn.close()
            return jsonify({'status': 'success'})
        except Exception as e:
            if conn: conn.rollback(); conn.close()
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/inventory/products', methods=['GET', 'POST', 'DELETE'])
@app.route('/api/inventory/products/<int:prod_id>', methods=['DELETE'])
def inventory_products(prod_id=None):
    conn = get_db_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'GET':
        cursor.execute("SELECT * FROM products ORDER BY category, name")
        res = cursor.fetchall()
        conn.close()
        for p in res:
            p['price'] = float(p['price'] or 0)
            p['bizz'] = float(p.get('bizz') or 0)
            if p.get('expiry_date'): p['expiry_date'] = p['expiry_date'].isoformat()
        return jsonify(res)
        
    elif request.method == 'POST':
        data = request.json
        pid = data.get('id')
        try:
            if pid:
                cursor.execute("""
                    UPDATE products SET barcode=%s, name=%s, category=%s, price=%s, bizz=%s, unit=%s, expiry_date=%s, min_threshold=%s
                    WHERE id = %s
                """, (data['barcode'], data['name'], data['category'], data['price'], data['bizz'], 
                      data.get('unit', 'PCS'), data.get('expiry_date'), data.get('min_threshold', 25), pid))
                log_audit(cursor, 'EDIT_PRODUCT', 'products', pid, None, data['name'])
            else:
                cursor.execute("""
                    INSERT INTO products (barcode, name, category, price, bizz, unit, expiry_date, min_threshold)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (data['barcode'], data['name'], data['category'], data['price'], data['bizz'], 
                      data.get('unit', 'PCS'), data.get('expiry_date'), data.get('min_threshold', 25)))
                log_audit(cursor, 'ADD_PRODUCT', 'products', cursor.lastrowid, None, data['name'])
            
            conn.commit(); conn.close()
            return jsonify({'status': 'success'})
        except Exception as e:
            if conn: conn.rollback(); conn.close()
            return jsonify({'status': 'error', 'message': str(e)}), 500
            
    elif request.method == 'DELETE':
        pid = prod_id or request.json.get('id')
        try:
            cursor.execute("DELETE FROM products WHERE id = %s", (pid,))
            conn.commit(); conn.close()
            return jsonify({'status': 'success'})
        except Exception as e:
            if conn: conn.rollback(); conn.close()
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/stock/transfer', methods=['POST'])
def api_stock_transfer():
    data = request.json
    items = data.get('items', [])
    from_loc = data.get('from_location')
    to_loc = data.get('to_location')
    transfer_type = data.get('type', 'out') # 'in' or 'out'
    reference = data.get('reference', 'GEN-TRF')

    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'DB fail'}), 500
    
    try:
        cursor = conn.cursor(dictionary=True)
        for item in items:
            pid = item['id']
            qty = float(item['qty'])
            diff = qty if transfer_type == 'in' else -qty
            
            # 1. Update stock
            cursor.execute("UPDATE products SET current_stock = current_stock + %s WHERE id = %s", (diff, pid))
            
            # 2. Log transfer
            cursor.execute("SELECT barcode, name FROM products WHERE id = %s", (pid,))
            p = cursor.fetchone()
            if p:
                cursor.execute("""
                    INSERT INTO stock_transfers (product_barcode, product_name, qty, from_location, to_location, pushed_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (p['barcode'], p['name'], qty, from_loc, to_loc, f"Admin (Ref: {reference})"))
                
        conn.commit(); conn.close()
        return jsonify({'status': 'success'})
    except Exception as e: 
        if conn: conn.rollback(); conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

import threading
import webbrowser
import time
try:
    import webview
except ImportError:
    webview = None

def run_flask():
    app.run(host=Config.SERVER_HOST, port=Config.SERVER_PORT, debug=False, use_reloader=False)

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(2)
    try:
        host = Config.SERVER_HOST if Config.SERVER_HOST != '0.0.0.0' else '127.0.0.1'
        url = f"http://{host}:{Config.SERVER_PORT}/"
        if webview:
            print("Launching Desktop Window...")
            webview.create_window("Maple Pro- Billing System", url, width=1280, height=800, min_size=(1024, 768))
            webview.start()
        else:
            webbrowser.open(url)
            while True: time.sleep(100)
    except Exception as e:
        print(f"Webview setup failed: {e}")
        webbrowser.open(url)
        while True: time.sleep(100)
