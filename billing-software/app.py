import platform
import sys
import collections
if sys.platform == "win32":
    Uname = collections.namedtuple("uname_result", ["system", "node", "release", "version", "machine", "processor"])
    platform.uname = lambda: Uname("Windows", "PC", "10", "10.0.19041", "AMD64", "AMD64")
    platform.system = lambda: "Windows"
    platform.release = lambda: "10"
    platform.machine = lambda: "AMD64"
    platform.version = lambda: "10.0.19041"
    
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, Response
import mysql.connector
import mysql.connector.locales.eng
from mysql.connector import pooling
import datetime
import sys
import os
import json
import queue
import time
from config import Config

def is_cloud_enabled():
    return False

def get_effective_mode():
    return 'local'

def is_local_only():
    return True

def is_cloud_only():
    return False

def is_hybrid():
    return False

def is_cloud_available():
    return False

from backend.sales import create_bill
from backend.network_diagnostics import (
    get_network_interfaces,
    scan_local_network,
    get_cached_scan_results,
    save_device_label,
    get_live_traffic,
    get_bandwidth_by_device,
    scan_ports,
    get_wifi_info,
    check_dns_gateway_health,
    generate_system_alerts,
    load_alerts_log,
    is_admin
)
from thermal_printer import print_thermal_bill, print_closure_report
import sqlite3
import subprocess
import socket
import threading
from flask_socketio import SocketIO, emit
from engineio.async_drivers import threading as engineio_threading

# Load local .env variables dynamically (Zero-dependency dotenv support)
if getattr(sys, 'frozen', False):
    exe_dir = os.path.dirname(sys.executable)
    if os.path.exists(os.path.join(exe_dir, ".env")):
        base_dir = exe_dir
    else:
        base_dir = getattr(sys, '_MEIPASS', exe_dir)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(base_dir, ".env")

# Set runtime default environment variables
os.environ.setdefault("GROQ_API_KEY", "YOUR_GROQ_API_KEY")
os.environ.setdefault("FORECASTING_PASSWORD", "1234")

# If .env does not exist, automatically initialize it with defaults
if not os.path.exists(env_path):
    try:
        with open(env_path, "w", encoding="utf-8") as env_file:
            env_file.write("GROQ_API_KEY=YOUR_GROQ_API_KEY\n")
            env_file.write("FORECASTING_PASSWORD=1234\n")
    except Exception as e:
        print(f"Error creating default .env: {e}")

if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

# Safe win32 window automation support
try:
    import win32gui
    import win32con
except ImportError:
    win32gui = None
    win32con = None

LARAGON_PATH = r"D:\laragon\laragon.exe" if os.path.exists(r"D:\laragon\laragon.exe") else r"C:\laragon\laragon.exe"

def is_process_running(name):
    """Check if a Windows process is active."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {name}"],
            capture_output=True, text=True
        )
        return name.lower() in result.stdout.lower()
    except:
        return False

def is_port_open(port, host="127.0.0.1", timeout=1.0):
    """Verify if a TCP port is responding."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except:
        return False

def init_self_healing_db():
    """Build local SQLite cache for all autopilot self-healing operations."""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "self_healing.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS healing_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            service TEXT,
            status TEXT,
            error_msg TEXT,
            action_taken TEXT,
            ai_diagnosis TEXT
        )
    """)
    # Backup history table — stores log of every backup operation
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS backup_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            backup_name  TEXT NOT NULL,
            backup_date  TEXT,
            backup_time  TEXT,
            size_bytes   INTEGER DEFAULT 0,
            backup_type  TEXT DEFAULT 'Manual',
            status       TEXT DEFAULT 'Unknown',
            duration_sec REAL DEFAULT 0,
            error_msg    TEXT DEFAULT '',
            location     TEXT DEFAULT '',
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_self_healing_db()

def log_healing_event(service, status, error_msg, action_taken):
    """Save fault/healed logs to SQLite."""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "self_healing.db")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO healing_logs (service, status, error_msg, action_taken, ai_diagnosis)
            VALUES (?, ?, ?, ?, ?)
        """, (service, status, error_msg, action_taken, "AI Diagnosis pending selection..."))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[SQLite Log Error] {e}")

# Track local IP changes
last_known_local_ip = "127.0.0.1"

def auto_click_ok():
    """Watch for Laragon license/warning popups and automatically click OK."""
    if not win32gui or not win32con:
        return
    time.sleep(3)
    for _ in range(15):
        hwnd = win32gui.FindWindow(None, "Warning")
        if hwnd:
            ok_btn = win32gui.FindWindowEx(hwnd, None, "Button", "OK")
            if ok_btn:
                win32gui.PostMessage(ok_btn, win32con.WM_LBUTTONDOWN, 0, 0)
                win32gui.PostMessage(ok_btn, win32con.WM_LBUTTONUP,   0, 0)
                print("[OK] Laragon popup auto-closed via Autopilot!")
                return
        time.sleep(1)




# IT Autopilot AI Metrics, Predictions, and Simulation Flags
MYSQL_HEALTH_HISTORY = []  # List of metrics dicts: {'timestamp': str, 'response_time': float, 'query_speed': float, 'status': str}
MYSQL_DOWNTIME_RISK = {
    'level': 'LOW',
    'score': 0,
    'advisory': 'Normal baseline latency detected. Database connection is healthy.'
}
SIMULATED_MYSQL_DELAY = 0.0  # mock query delay in seconds (e.g., 0.8)
SIMULATED_MYSQL_FAILURES = False  # mock complete failure
LAST_AI_ADVISORY_FETCH_TIME = 0.0  # rate limit tracker for Groq calls

def generate_ai_prediction_advisory_async(recent_avg_rt, failures_count, level, score):
    def fetch_job():
        global MYSQL_DOWNTIME_RISK
        groq_api_key = os.environ.get("GROQ_API_KEY", "")
        if not groq_api_key:
            return
            
        import requests
        prompt = (
            "You are 'IT Autopilot AI Specialist' for MaplePro Billing Systems.\n"
            "Generate a predictive warning/advisory alert for the local MySQL database.\n"
            f"Current stats: Average Latency is {recent_avg_rt:.1f}ms, Connection Drops is {failures_count} in the last 10 checks.\n"
            f"Calculated Risk Level is {level} (Score {score}%).\n"
            "Explain what symptoms the AI has detected, warning them before the database goes down, "
            "and suggest one quick advisory action (e.g. check concurrent transactions, restart Laragon service, or optimize slow queries).\n"
            "Format: Output a single paragraph. Keep it concise, professional, and clear. Do not use markdown."
        )
        
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "You are a professional IT system administrator. Answer in a single short paragraph under 3 sentences without markdown."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5,
            "max_tokens": 150
        }
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {groq_api_key}", "Content-Type": "application/json"},
                timeout=5
            )
            if r.status_code == 200:
                ai_text = r.json()["choices"][0]["message"]["content"].strip()
                MYSQL_DOWNTIME_RISK['advisory'] = f"🤖 AI PREDICTIVE ALERT: {ai_text}"
        except Exception as e:
            print(f"[AI Advisor Fetch Error] {e}")
            
    import threading
    threading.Thread(target=fetch_job, daemon=True).start()

def update_downtime_risk_prediction():
    global MYSQL_DOWNTIME_RISK, LAST_AI_ADVISORY_FETCH_TIME
    history = MYSQL_HEALTH_HISTORY
    if not history:
        return
        
    latest = history[-1]
    
    if latest['status'] == 'OFFLINE':
        MYSQL_DOWNTIME_RISK = {
            'level': 'CRITICAL',
            'score': 100,
            'advisory': 'CRITICAL WARNING: Local MySQL service is offline. Failover is active.'
        }
        return
        
    recent_checks = history[-5:]
    older_checks = history[:-5] if len(history) > 5 else history
    
    recent_avg_rt = sum(c['response_time'] for c in recent_checks) / len(recent_checks)
    older_avg_rt = sum(c['response_time'] for c in older_checks) / len(older_checks)
    
    failures_in_history = sum(1 for c in history[-10:] if c['status'] == 'OFFLINE')
    
    score = 0
    
    # 1. Base latency check
    if recent_avg_rt > 1000:
        score += 60
    elif recent_avg_rt > 500:
        score += 40
    elif recent_avg_rt > 200:
        score += 20
    elif recent_avg_rt > 50:
        score += 10
        
    # 2. Performance degradation speed (velocity penalty)
    if older_avg_rt > 0 and recent_avg_rt > older_avg_rt * 2.0:
        score += 25
    elif older_avg_rt > 0 and recent_avg_rt > older_avg_rt * 1.5:
        score += 15
        
    # 3. Connection drop frequency penalty
    if failures_in_history > 0:
        score += failures_in_history * 15
        
    score = min(score, 95)
    
    # Map score to level
    if score >= 70:
        level = 'HIGH'
        advisory = f"WARNING: High downtime risk detected ({score}%). Latency has spiked to {round(recent_avg_rt, 1)}ms with query performance deterioration. Rerouting warning active."
    elif score >= 30:
        level = 'MEDIUM'
        advisory = f"ADVISORY: Moderate downtime risk detected ({score}%). Response time is degraded ({round(recent_avg_rt, 1)}ms). Autopilot is monitoring."
    else:
        level = 'LOW'
        advisory = f"HEALTHY: Low downtime risk ({score}%). MySQL response is optimal ({round(recent_avg_rt, 1)}ms)."
        
    import time
    current_time = time.time()
    if level in ('MEDIUM', 'HIGH') and (current_time - LAST_AI_ADVISORY_FETCH_TIME > 60.0):
        LAST_AI_ADVISORY_FETCH_TIME = current_time
        generate_ai_prediction_advisory_async(recent_avg_rt, failures_in_history, level, score)
        MYSQL_DOWNTIME_RISK = {
            'level': level,
            'score': score,
            'advisory': advisory
        }
    else:
        if level in ('MEDIUM', 'HIGH') and MYSQL_DOWNTIME_RISK['level'] == level and '🤖 AI' in MYSQL_DOWNTIME_RISK['advisory']:
            MYSQL_DOWNTIME_RISK['score'] = score
        else:
            MYSQL_DOWNTIME_RISK = {
                'level': level,
                'score': score,
                'advisory': advisory
            }


BACKGROUND_QUEUE_MAX = 200
BACKGROUND_WORK_QUEUE = queue.Queue(maxsize=BACKGROUND_QUEUE_MAX)


def background_worker_loop():
    """Run post-bill work through one shared queue so billing never spawns unlimited threads."""
    while True:
        task = BACKGROUND_WORK_QUEUE.get()
        try:
            task_type = task.get('type')
            if task_type == 'brain':
                evolve_brain_realtime(task.get('bill_id'))
        except Exception as e:
            print(f"[BACKGROUND WORKER ERROR] {e}")
        finally:
            BACKGROUND_WORK_QUEUE.task_done()


def enqueue_background_task(task):
    try:
        BACKGROUND_WORK_QUEUE.put_nowait(task)
        return True
    except queue.Full:
        print(f"[BACKGROUND QUEUE FULL] Dropped {task.get('type')} task.")
        return False


def schedule_brain_evolution(bill_id=None):
    enqueue_background_task({'type': 'brain', 'bill_id': bill_id})


def trigger_immediate_sync():
    """Request cloud sync without blocking the request thread; requests are debounced."""
    pass


threading.Thread(target=background_worker_loop, daemon=True).start()

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

    def disconnect(self, q):
        if q in self.listeners:
            try:
                self.listeners.remove(q)
            except ValueError:
                pass

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
DOCUMENTS_FOLDER = os.path.join(os.path.expanduser("~"), "Documents", "SagarSoftware")
if not os.path.exists(DOCUMENTS_FOLDER):
    os.makedirs(DOCUMENTS_FOLDER)

app = Flask(__name__, 
            template_folder=resource_path('frontend'), 
            static_folder=resource_path('frontend'), 
            static_url_path='')
app.secret_key = Config.SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

@app.after_request
def add_cache_control_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

def format_sse(data: str, event=None) -> str:
    msg = f'data: {data}\n\n'
    if event:
        msg = f'event: {event}\n{msg}'
    return msg

@app.route('/api/realtime/stream')
def realtime_stream():
    def stream():
        q = announcer.listen()
        try:
            while True:
                try:
                    msg = q.get(timeout=15) # Wait up to 15s for an update
                    yield format_sse(data=msg, event='billing_update')
                except queue.Empty:
                    # Keep-alive ping to detect client disconnects
                    yield ': keep-alive\n\n'
        except (GeneratorExit, Exception):
            pass
        finally:
            announcer.disconnect(q)
    return Response(stream(), mimetype='text/event-stream')

db_pool = None
db_pool_warming = False
db_pool_lock = threading.Lock()




def log_error(msg):
    try:
        log_path = os.path.join(getattr(Config, 'ACTIVE_CONFIG_PATH', '.').replace('config.json', ''), 'connection_debug.txt')
        with open(log_path, 'a') as f:
            f.write(f"[{datetime.datetime.now()}] {msg}\n")
    except: pass

def get_db_pool():
    global db_pool, db_pool_warming
    if db_pool is None:
        try:
            with db_pool_lock:
                if db_pool is None:
                    effective_pool_size = max(1, min(int(Config.MYSQL_POOL_SIZE), 20))
                    db_pool = pooling.MySQLConnectionPool(
                        pool_name=Config.MYSQL_POOL_NAME,
                        pool_size=effective_pool_size,
                        host=Config.MYSQL_HOST,
                        port=Config.MYSQL_PORT,
                        user=Config.MYSQL_USER,
                        password=Config.MYSQL_PASSWORD,
                        database=Config.MYSQL_DB,
                        autocommit=Config.MYSQL_AUTOCOMMIT,
                        connection_timeout=1,
                        ssl_disabled=True,
                    )
        except Exception as e:
            err_msg = f"CRITICAL Pool Error: {e}"
            print(err_msg)
            log_error(err_msg)
            db_pool = None
        finally:
            db_pool_warming = False
    return db_pool

def warm_db_pool_async():
    global db_pool_warming
    if db_pool is not None or db_pool_warming:
        return
    db_pool_warming = True
    threading.Thread(target=get_db_pool, daemon=True).start()

# Global database status tracker
DB_STATUS = "local"
MYSQL_IS_ALIVE = True
CLOUD_IS_ALIVE = False
SYNC_SYSTEM_MODE = "LOCAL_PRIMARY"
LAST_CONNECTION_ERROR = None

def get_local_db_connection():
    global MYSQL_IS_ALIVE, DB_STATUS
    try:
        pool = db_pool
        if pool:
            conn = pool.get_connection()
            conn.autocommit = Config.MYSQL_AUTOCOMMIT
            cursor = conn.cursor()
            cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
            cursor.execute("SET SESSION innodb_lock_wait_timeout = 5")
            cursor.close()
            MYSQL_IS_ALIVE = True
            return conn
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB,
            connection_timeout=2,
            autocommit=Config.MYSQL_AUTOCOMMIT,
            ssl_disabled=True
        )
        cursor = conn.cursor()
        cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
        cursor.execute("SET SESSION innodb_lock_wait_timeout = 5")
        cursor.close()
        MYSQL_IS_ALIVE = True
        return conn
    except Exception as e:
        MYSQL_IS_ALIVE = False
        return None

def get_db_connection():
    global DB_STATUS, MYSQL_IS_ALIVE
    conn = get_local_db_connection()
    if conn:
        DB_STATUS = "local"
        return conn
    DB_STATUS = "local_offline"
    return None


RETRYABLE_DB_ERROR_CODES = {1205, 1213, 2006, 2013, 2055}
RETRYABLE_DB_ERROR_TEXT = (
    'deadlock',
    'lock wait timeout',
    'lost connection',
    'server has gone away',
    'connection timed out',
    'wait operation timed out',
)


def is_retryable_db_error(exc):
    errno = getattr(exc, 'errno', None)
    if errno in RETRYABLE_DB_ERROR_CODES:
        return True
    message = str(exc).lower()
    return any(token in message for token in RETRYABLE_DB_ERROR_TEXT)


def ensure_billing_performance_indexes():
    if is_cloud_only():
        return
    index_statements = (
        "CREATE INDEX idx_bills_date_status_created_by ON bills (bill_date, status, created_by)",
        "CREATE INDEX idx_bill_items_bill_id ON bill_items (bill_id)",
        "CREATE INDEX idx_bill_items_product_name ON bill_items (product_name)",
        "CREATE INDEX idx_stock_movements_bill_id ON stock_movements (bill_id)",
        "CREATE INDEX idx_returns_log_bill_id ON returns_log (bill_id)",
        "CREATE INDEX idx_returns_log_product_code ON returns_log (product_code)",
        "CREATE INDEX idx_returns_log_return_date ON returns_log (return_date)",
        "CREATE INDEX idx_audit_logs_table_name ON audit_logs (table_name)",
        "CREATE INDEX idx_audit_logs_record_id ON audit_logs (record_id)",
        "CREATE INDEX idx_audit_logs_action ON audit_logs (action)",
        "CREATE INDEX idx_denominations_balance_id ON denominations (balance_id)",
        "CREATE INDEX idx_sync_queue_status ON sync_queue (status)",
        "CREATE INDEX idx_sync_queue_invoice_no ON sync_queue (invoice_no)",
        "CREATE INDEX idx_sync_queue_table_name ON sync_queue (table_name)",
    )
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB,
            connection_timeout=2,
            autocommit=True,
            ssl_disabled=True
        )
        cursor = conn.cursor()
        for statement in index_statements:
            try:
                cursor.execute(statement)
            except mysql.connector.Error as e:
                if e.errno not in (1061, 1146, 1072):
                    print(f"[Startup] Index skipped: {e}")
    except Exception as e:
        print(f"[Startup] Billing index check skipped: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_login_db_connection():
    global DB_STATUS, MYSQL_IS_ALIVE, LAST_CONNECTION_ERROR
    LAST_CONNECTION_ERROR = None
    try:
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB,
            connection_timeout=2,
            autocommit=Config.MYSQL_AUTOCOMMIT,
            ssl_disabled=True
        )
        cursor = conn.cursor()
        cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
        cursor.close()
        MYSQL_IS_ALIVE = True
        DB_STATUS = "local"
        return conn
    except Exception as e:
        log_error(f"[LOGIN DB ERROR] Local MySQL: {e}")
        LAST_CONNECTION_ERROR = f"Local MySQL Error: {e}"
        MYSQL_IS_ALIVE = False
        DB_STATUS = "local_offline"
        return None

@app.route('/api/db-status')
def get_db_status_route():
    global DB_STATUS, MYSQL_IS_ALIVE
    if MYSQL_IS_ALIVE:
        return jsonify({
            'status': 'local',
            'label': 'Local MySQL',
            'color': '#10b981',
            'mode': 'local',
            'alive': True
        })
    return jsonify({
        'status': 'local_offline',
        'label': 'Local Server is OFF',
        'color': '#ef4444',
        'mode': 'local',
        'alive': False
    })

@app.route('/api/config/server-ip', methods=['GET', 'POST'])
def manage_server_ip():
    if request.method == 'GET':
        return jsonify({
            'current_ip': Config.MYSQL_HOST,
            'db_mode': 'local',
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
        
        # 3. Reset DB Pool to force reconnect
        global db_pool
        db_pool = None 
        
        return jsonify({
            'status': 'success', 
            'message': f'Server configuration updated (IP: {new_ip}). Settings applied instantly.'
            })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/system/reset-db', methods=['POST'])
def reset_database_route():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    data = request.json
    mode = data.get('mode') # 'financial_year' or 'factory'
    password = data.get('password')
    
    # Verify Admin Password
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT password_hash FROM users WHERE username = %s", (session.get('username'),))
    user = cursor.fetchone()
    
    if not user or user['password_hash'] != password:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Incorrect security password.'}), 401

    try:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        if mode == 'financial_year':
            # 1. Summarize and build the Memory Bank (seasonal_history) before clearing transactions
            try:
                cursor.execute("""
                    SELECT 
                        EXTRACT(YEAR FROM b.bill_date) as yr,
                        EXTRACT(MONTH FROM b.bill_date) as mth,
                        COALESCE(p.category, 'General') as cat,
                        SUM(bi.qty) as monthly_qty
                    FROM bills b
                    JOIN bill_items bi ON b.id = bi.bill_id
                    LEFT JOIN products p ON bi.product_name = p.name
                    WHERE b.status != 'Cancelled' AND b.bill_date IS NOT NULL
                    GROUP BY EXTRACT(YEAR FROM b.bill_date), EXTRACT(MONTH FROM b.bill_date), COALESCE(p.category, 'General')
                """)
                rows = cursor.fetchall()
                
                cat_monthly_sales = {}
                for r in rows:
                    yr = int(r['yr'])
                    mth = int(r['mth'])
                    cat = str(r['cat']).strip()
                    qty = float(r['monthly_qty'] or 0.0)
                    
                    if cat not in cat_monthly_sales:
                        cat_monthly_sales[cat] = {}
                    cat_monthly_sales[cat][(yr, mth)] = qty
                
                for cat, monthly_dict in cat_monthly_sales.items():
                    qtys = list(monthly_dict.values())
                    if qtys:
                        avg_qty = sum(qtys) / len(qtys)
                        if avg_qty <= 0:
                            avg_qty = 1.0
                        for (yr, mth), qty in monthly_dict.items():
                            multiplier = qty / avg_qty
                            multiplier = max(0.1, min(10.0, multiplier))
                            
                            # Clean up old values to prevent unique constraint failures
                            cursor.execute("""
                                DELETE FROM seasonal_history 
                                WHERE year = %s AND month = %s AND category = %s
                            """, (yr, mth, cat))
                            
                            cursor.execute("""
                                INSERT INTO seasonal_history (year, month, category, multiplier)
                                VALUES (%s, %s, %s, %s)
                            """, (yr, mth, cat, round(multiplier, 2)))
                print("[AI AUTOPILOT] Seasonal history memory bank compiled successfully before database reset.")
            except Exception as hist_err:
                print(f"[AI AUTOPILOT WARNING] Failed to compile seasonal history: {hist_err}")
                log_error(f"Failed to compile seasonal history during reset: {hist_err}")
                # CRITICAL: rollback any aborted transaction state so subsequent queries work
                try:
                    conn.rollback()
                except Exception:
                    pass

            # Clear all transactional data but keep products and users
            tables = [
                'bills', 'bill_items', 'bill_sequences', 'returns_log', 
                'stock_movements', 'expenses', 'audit_logs', 'account_entries', 
                'cash_balance', 'denominations'
            ]
            for table in tables:
                cursor.execute(f"TRUNCATE TABLE {table}")
            
            # Note: Stock levels are kept as 'Opening Stock' for the new year
            log_audit(cursor, 'SYSTEM_RESET', 'database', 0, 'ALL_DATA', 'Financial Year Reset Executed')
            msg = "Financial Year Reset complete. Sales and expenses cleared."

        elif mode == 'factory':
            # Wipe everything except users
            tables = [
                'bills', 'bill_items', 'bill_sequences', 'returns_log', 
                'stock_movements', 'expenses', 'products', 'categories',
                'audit_logs', 'account_entries', 'cash_balance', 'denominations',
                'daily_position_list'
            ]
            for table in tables:
                cursor.execute(f"TRUNCATE TABLE {table}")
            
            # Restore default users just in case
            cursor.execute("TRUNCATE TABLE users")
            default_users = [
                ('admin', 'admin123', 'admin'),
                ('counter', '123', 'sales'),
                ('accountant', 'account123', 'account')
            ]
            cursor.executemany("INSERT IGNORE INTO users (username, password_hash, role) VALUES (%s, %s, %s)", default_users)
            
            msg = "System wiped successfully. All products and sales cleared."

        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        return jsonify({'status': 'success', 'message': msg})
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({'status': 'error', 'message': f"Reset failed: {str(e)}"}), 500
    finally:
        if conn: conn.close()




def fetch_database_size_kb(cursor):
    try:
        cursor.execute("SELECT DATABASE()")
        db_name = cursor.fetchone()
        db_name = (db_name[0] if isinstance(db_name, tuple) else db_name.get('DATABASE()', '')) if db_name else ''
        
        if not db_name:
            return 160.0
            
        cursor.execute("""
            SELECT SUM(data_length + index_length) / 1024 AS size_kb 
            FROM information_schema.TABLES 
            WHERE table_schema = %s
        """, (db_name,))
        row = cursor.fetchone()
        size_kb = float((row[0] if isinstance(row, tuple) else row.get('SUM(data_length + index_length) / 1024', 160.0)) or 160.0)
        return size_kb
    except Exception as e:
        print(f"[DB SIZE ERROR] {e}")
        return 160.0

def fetch_brain_state_stats(cursor):
    # 1. Total products count
    cursor.execute("SELECT COUNT(*) FROM products")
    products_count = cursor.fetchone()
    products_count = (products_count[0] if isinstance(products_count, tuple) else products_count.get('COUNT(*)', 0)) if products_count else 0

    # 2. Total categories count
    cursor.execute("SELECT COUNT(DISTINCT category) FROM products")
    categories_count = cursor.fetchone()
    categories_count = (categories_count[0] if isinstance(categories_count, tuple) else categories_count.get('COUNT(DISTINCT category)', 0)) if categories_count else 0

    # 3. Historical bills count
    cursor.execute("SELECT COUNT(*) FROM bills")
    bills_count = cursor.fetchone()
    bills_count = (bills_count[0] if isinstance(bills_count, tuple) else bills_count.get('COUNT(*)', 0)) if bills_count else 0

    # 4. Expense accounts count
    cursor.execute("SELECT COUNT(*) FROM expenses")
    expenses_count = cursor.fetchone()
    expenses_count = (expenses_count[0] if isinstance(expenses_count, tuple) else expenses_count.get('COUNT(*)', 0)) if expenses_count else 0

    # 5. Low stock alerts count
    cursor.execute("SELECT COUNT(*) FROM products WHERE current_stock <= min_threshold")
    low_stock_count = cursor.fetchone()
    low_stock_count = (low_stock_count[0] if isinstance(low_stock_count, tuple) else low_stock_count.get('COUNT(*)', 0)) if low_stock_count else 0

    # 6. Today's sales
    cursor.execute("SELECT SUM(total_amount) FROM bills WHERE DATE(bill_date) = CURDATE() AND status != 'Cancelled'")
    today_sales_row = cursor.fetchone()
    today_sales = float((today_sales_row[0] if isinstance(today_sales_row, tuple) else today_sales_row.get('SUM(total_amount)', 0)) or 0)

    # 7. Monthly expenses
    today = datetime.date.today()
    start_of_month = datetime.date(today.year, today.month, 1)
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE expense_date >= %s", (start_of_month,))
    monthly_expenses_row = cursor.fetchone()
    monthly_expenses = float((monthly_expenses_row[0] if isinstance(monthly_expenses_row, tuple) else monthly_expenses_row.get('SUM(amount)', 0)) or 0)

    # 8. Weekly sales
    cursor.execute("SELECT SUM(total_amount) FROM bills WHERE bill_date >= DATE_SUB(NOW(), INTERVAL 7 DAY) AND status != 'Cancelled'")
    weekly_sales_row = cursor.fetchone()
    weekly_sales = float((weekly_sales_row[0] if isinstance(weekly_sales_row, tuple) else weekly_sales_row.get('SUM(total_amount)', 0)) or 0)

    # 9. Database size in KB
    db_size_kb = fetch_database_size_kb(cursor)

    return {
        'products_count': products_count,
        'categories_count': categories_count,
        'bills_count': bills_count,
        'expenses_count': expenses_count,
        'low_stock_count': low_stock_count,
        'today_sales': today_sales,
        'monthly_expenses': monthly_expenses,
        'weekly_sales': weekly_sales,
        'db_size_kb': db_size_kb
    }

def fetch_recent_neural_logs(limit=10):
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "self_healing.db")
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, service, status, action_taken 
            FROM healing_logs 
            WHERE service = 'NEURAL_CORE' 
            ORDER BY id DESC 
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        logs = []
        for r in rows:
            logs.append({
                'id': r['id'],
                'timestamp': r['timestamp'],
                'service': r['service'],
                'status': r['status'],
                'action_taken': r['action_taken']
            })
        conn.close()
        
        if not logs:
            log_healing_event('NEURAL_CORE', 'SYSTEM_INIT', '', 'Neural Network Core initialized successfully.')
            log_healing_event('NEURAL_CORE', 'WEIGHTS_LOADED', '', 'Synaptic weight matrix loaded. Size: 8.42M params.')
            log_healing_event('NEURAL_CORE', 'AUTOPILOT_ON', '', 'Continuous learning autopilot engaged. Standby for sales.')
            return fetch_recent_neural_logs(limit)
            
        return logs
    except Exception as e:
        print(f"[SQLite Read Error] {e}")
        return []

def generate_brain_cognitive_insight(cursor):
    # 1. Gather stats for context
    cursor.execute("SELECT SUM(total_amount) as total FROM bills WHERE bill_date >= DATE_SUB(NOW(), INTERVAL 7 DAY) AND status != 'Cancelled'")
    weekly_sales_res = cursor.fetchone()
    weekly_sales = (weekly_sales_res['total'] if isinstance(weekly_sales_res, dict) else weekly_sales_res[0]) or 0
    
    cursor.execute("""
        SELECT category, SUM(amount) as revenue 
        FROM bill_items bi
        LEFT JOIN products p ON bi.product_name = p.name 
        JOIN bills b ON bi.bill_id = b.id
        WHERE b.status != 'Cancelled'
        GROUP BY category 
        ORDER BY revenue DESC 
        LIMIT 1
    """)
    top_cat = cursor.fetchone()
    
    cursor.execute("SELECT name, current_stock FROM products WHERE current_stock <= min_threshold LIMIT 5")
    low_stock = cursor.fetchall()
    
    groq_api_key = os.environ.get("GROQ_API_KEY", "")
    
    if groq_api_key:
        import requests
        import json
        
        top_cat_name = (top_cat['category'] if isinstance(top_cat, dict) else top_cat[0]) if top_cat else 'General'
        top_cat_rev = (top_cat['revenue'] if isinstance(top_cat, dict) else top_cat[1]) if top_cat else 0
        low_stock_str = ', '.join([p['name'] + ' (Stock:' + str(p['current_stock']) + ')' for p in low_stock]) if low_stock else 'None'
        
        prompt = (
            "You are the Neural Store Consultant for Sagar Super Billing Software.\n"
            "Review the following weekly store statistics and generate 3 concise, bulleted analytics observations (prefixed with 'Weekly Performance:', 'Dominance:', 'Momentum:') and 1 strategic business advice recommendation.\n"
            f"Context Data:\n"
            f"- Last 7 Days Sales Revenue: INR {float(weekly_sales):,.2f}\n"
            f"- Top Revenue Category: {top_cat_name} (Revenue: INR {float(top_cat_rev):,.2f})\n"
            f"- Low Stock Alert Products (critical count): {low_stock_str}\n\n"
            "Return the response in raw JSON format with two keys: 'analysis' (array of strings, exactly 3 items) and 'advice' (array of strings, exactly 1 item). Do not wrap in markdown or backticks."
        )
        
        try:
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"}
                },
                headers={"Authorization": f"Bearer {groq_api_key}", "Content-Type": "application/json"},
                timeout=8
            )
            if r.status_code == 200:
                res_json = r.json()
                content = json.loads(res_json["choices"][0]["message"]["content"])
                return {
                    'analysis': content.get('analysis', []),
                    'advice': content.get('advice', [])
                }
        except Exception as e:
            print(f"[LLM INSIGHT ERROR] Groq API call failed: {e}")

    # Local fallback
    top_cat_name = (top_cat['category'] if isinstance(top_cat, dict) else top_cat[0]) if top_cat else 'N/A'
    insights = [
        f"Weekly Performance: Generated \u20B9{float(weekly_sales):,.2f} in sales this week.",
        f"Dominance: '{top_cat_name}' remains your top revenue anchor.",
        "Momentum: Real-time sales velocities mapped. Forecast curves aligned."
    ]
    if low_stock:
        insights.append(f"Inventory Risk: {len(low_stock)} items are under safety threshold levels.")
        
    advice = []
    if float(weekly_sales) > 10000:
        advice.append("Strategy: Setup dynamic loyalty rewards for high-frequency shoppers to stabilize revenue.")
    else:
        advice.append("Strategy: Implement an afternoon 'UPI discount' between 2PM-4PM to boost traffic during quiet hours.")
        
    return {
        'analysis': insights[:3],
        'advice': advice[:1]
    }

def evolve_brain_realtime(bill_id=None):
    try:
        import math
        conn = get_login_db_connection()
        if not conn:
            print("[NEURAL CORE ERROR] DB Connection failed during evolution")
            return
        cursor = conn.cursor(dictionary=True)
        
        # 1. Initialize calibration log
        bill_display = f"Bill ID {bill_id}" if bill_id else "All Products"
        log_healing_event('NEURAL_CORE', 'CALIBRATING', '', f'Initializing network weight optimization for {bill_display}.')
            
        # 2. Adjust category forecasting multipliers in seasonal_history based on recent sales velocity
        cursor.execute("""
            SELECT category, SUM(bi.qty) as cat_qty 
            FROM bill_items bi
            JOIN products p ON bi.product_name = p.name
            JOIN bills b ON bi.bill_id = b.id
            WHERE b.status != 'Cancelled' AND b.bill_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            GROUP BY category
        """)
        cat_sales = cursor.fetchall()
        
        today = datetime.date.today()
        updated_categories = 0
        for cat in cat_sales:
            category = cat['category']
            if not category: continue
            qty = float(cat['cat_qty'] or 0)
            
            # Base multiplier model: adjust seasonal scaling factor
            avg_qty_per_cat = 50.0  # reference baseline
            multiplier = max(0.8, min(2.5, round(qty / avg_qty_per_cat, 2)))
            
            # Check if multiplier changed
            cursor.execute("""
                SELECT multiplier FROM seasonal_history 
                WHERE year = %s AND month = %s AND category = %s
            """, (today.year, today.month, category))
            hist_info = cursor.fetchone()
            current_mult = float((hist_info['multiplier'] if isinstance(hist_info, dict) else hist_info[0]) if hist_info else 0)
            
            if multiplier != current_mult:
                cursor.execute("""
                    INSERT INTO seasonal_history (year, month, category, multiplier)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE multiplier = %s
                """, (today.year, today.month, category, multiplier, multiplier))
                log_healing_event('NEURAL_CORE', 'MULTIPLIER_ADJUSTED', '', f"Calibrated category '{category}' multiplier to {multiplier}")
                updated_categories += 1
            
        conn.commit()
        
        # 3. Retrieve final stats, insights, and logs
        stats = fetch_brain_state_stats(cursor)
        insights = generate_brain_cognitive_insight(cursor)
        
        conn.close()
        
        # Write successful finish log
        log_msg = f"Network calibration complete. Optimized {updated_categories} category parameters."
        log_healing_event('NEURAL_CORE', 'SUCCESS', '', log_msg)
        
        recent_logs = fetch_recent_neural_logs(limit=10)
        
        # Emit real-time Socket update
        socketio.emit('brain_evolved', {
            'status': 'success',
            'bill_id': bill_id,
            'stats': stats,
            'insights': insights,
            'logs': recent_logs,
            'timestamp': datetime.datetime.now().isoformat()
        })
        print(f"[NEURAL CORE] Auto-evolved weights successfully. Emitters notified.")
    except Exception as e:
        print(f"[NEURAL CORE ERROR] Real-time calibration failed: {e}")
        log_healing_event('NEURAL_CORE', 'ERROR', str(e), 'Calibration cycle aborted due to system error.')

@app.route('/api/analytics/ai-insight')
def get_ai_insight():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
        
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 1. Gather Context for the AI
        cursor.execute("SELECT SUM(total_amount) as total FROM bills WHERE bill_date >= DATE_SUB(NOW(), INTERVAL 7 DAY) AND status != 'Cancelled'")
        weekly_sales = cursor.fetchone()['total'] or 0
        
        cursor.execute("""
            SELECT category, SUM(amount) as revenue 
            FROM bill_items bi
            LEFT JOIN products p ON bi.product_name = p.name 
            JOIN bills b ON bi.bill_id = b.id
            WHERE b.status != 'Cancelled'
            GROUP BY category 
            ORDER BY revenue DESC 
            LIMIT 1
        """)
        top_cat = cursor.fetchone()
        
        cursor.execute("SELECT name, current_stock FROM products WHERE current_stock <= min_threshold LIMIT 5")
        low_stock = cursor.fetchall()
        
        groq_api_key = os.environ.get("GROQ_API_KEY", "")
        
        if groq_api_key:
            import requests
            import json
            # Call Groq to generate dynamic strategic advice
            prompt = (
                "You are the Neural Store Consultant for Sagar Super Billing Software.\n"
                "Review the following weekly store statistics and generate 3 concise, bulleted analytics observations (prefixed with 'Weekly Performance:', 'Dominance:', 'Momentum:') and 1 strategic business advice recommendation.\n"
                f"Context Data:\n"
                f"- Last 7 Days Sales Revenue: INR {weekly_sales:,.2f}\n"
                f"- Top Revenue Category: {top_cat['category'] if top_cat else 'General'} (Revenue: INR {float(top_cat['revenue']) if top_cat else 0:,.2f})\n"
                f"- Low Stock Alert Products (critical count): {', '.join([p['name'] + ' (Stock:' + str(p['current_stock']) + ')' for p in low_stock]) if low_stock else 'None'}\n\n"
                "Return the response in raw JSON format with two keys: 'analysis' (array of strings, exactly 3 items) and 'advice' (array of strings, exactly 1 item). Do not wrap in markdown or backticks."
            )
            
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "response_format": {"type": "json_object"}
                    },
                    headers={"Authorization": f"Bearer {groq_api_key}", "Content-Type": "application/json"},
                    timeout=8
                )
                if r.status_code == 200:
                    res_json = r.json()
                    content = json.loads(res_json["choices"][0]["message"]["content"])
                    return jsonify({
                        'status': 'success',
                        'analysis': content.get('analysis', []),
                        'advice': content.get('advice', []),
                        'timestamp': datetime.datetime.now().isoformat()
                    })
            except Exception as e:
                print(f"[LLM INSIGHT ERROR] Groq API call failed: {e}")

        # Local fallback Rule-based AI Engine
        insights = [
            f"Weekly Performance: Generated \u20B9{weekly_sales:,.2f} in sales this week.",
            f"Dominance: '{top_cat['category'] if top_cat else 'N/A'}' remains your top revenue anchor.",
            "Momentum: Real-time sales velocities mapped. Forecast curves aligned."
        ]
        
        if low_stock:
            insights.append(f"Inventory Risk: {len(low_stock)} items are under safety threshold levels.")
            
        advice = []
        if weekly_sales > 10000:
            advice.append("Strategy: Setup dynamic loyalty rewards for high-frequency shoppers to stabilize revenue.")
        else:
            advice.append("Strategy: Implement an afternoon 'UPI discount' between 2PM-4PM to boost traffic during quiet hours.")

        return jsonify({
            'status': 'success',
            'analysis': insights,
            'advice': advice,
            'timestamp': datetime.datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

def log_audit(cursor, action, table_name, record_id, old_val=None, new_val=None):
    try:
        cursor.execute("""
            INSERT INTO audit_logs (user_id, action, table_name, record_id, old_value, new_value)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (session.get('username', 'SYSTEM'), action, table_name, record_id, str(old_val), str(new_val)))
    except Exception as e:
        print(f"Audit Log Error: {e}")

def check_and_init_db():
    if is_cloud_only():
        print("[DB INIT] Cloud-only mode. Skipping local MySQL initialization.")
        return
    print("Initializing Database...")
    try:
        # 1. Connect to MySQL Server
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            ssl_disabled=True
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
            )""",
            "daily_position_list": "CREATE TABLE IF NOT EXISTS daily_position_list (barcode VARCHAR(50) PRIMARY KEY)",
            "seasonal_history": """CREATE TABLE IF NOT EXISTS seasonal_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                year INT NOT NULL,
                month INT NOT NULL,
                category VARCHAR(50) NOT NULL,
                multiplier DECIMAL(5, 2) DEFAULT 1.00,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE INDEX (year, month, category)
            )""",
            "holidays": """CREATE TABLE IF NOT EXISTS holidays (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(50) NOT NULL UNIQUE,
                date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        
        # 6. Seed Daily Position List if empty
        cursor.execute("SELECT COUNT(*) FROM daily_position_list")
        if cursor.fetchone()[0] == 0:
            print("Seeding Daily Position list...")
            initial_codes = [
                '1100', '1101', '1102', '1103', '1104', '1105', '1106', '1107', '1108', '1109', '1110',
                '1150', '1151', '1152', '1153', '1154', '1235', '1236', '1239', '1240', '1241', '1333',
                '1350', '1351', '1352', '1354', '1358', '1446', '1600', '1606', '1610', '1612', '1654',
                '1655', '1656', '1660', '1661', '1662', '1722', '1723', '1726', '1820', '1821', '1822',
                '1823', '1824', '1825', '1826', '1827', '1828', '1830', '1831', '1832', '1833', '1834',
                '1909', '1910', '1950', '1951'
            ]
            for code in initial_codes:
                cursor.execute("INSERT IGNORE INTO daily_position_list (barcode) VALUES (%s)", (code,))
            conn.commit()

        # 7. Seed Default Holidays if empty
        cursor.execute("SELECT COUNT(*) FROM holidays")
        if cursor.fetchone()[0] == 0:
            print("Seeding Default Holidays...")
            current_year = datetime.date.today().year
            default_holidays = [
                ('Pongal', f"{current_year}-01-14"),
                ('Diwali', f"{current_year}-11-08")
            ]
            cursor.executemany("INSERT IGNORE INTO holidays (name, date) VALUES (%s, %s)", default_holidays)
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
    ensure_billing_performance_indexes()
    pass

@app.route('/')
def index():

    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_login_db_connection()
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
            flash('Database connection failed! Please check if the MySQL server PC is running.', 'error')
            
    return render_template('login.html', current_host=Config.MYSQL_HOST)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('admin/dashboard.html')

@app.route('/account/dashboard')
def account_dashboard():
    if session.get('role') != 'account':
        return redirect(url_for('login'))
    return render_template('account/dashboard.html')

@app.route('/account/entry')
def account_entry():
    if session.get('role') != 'account':
        return redirect(url_for('login'))
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
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('admin/intelligence/stock_intel.html')

@app.route('/admin/analytics')
def admin_analytics():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('admin/analytics.html')

@app.route('/admin/intelligence/brain')
def admin_intelligence_brain():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('admin/intelligence/brain_focus.html')

@app.route('/api/admin/intelligence/brain-state')
def get_brain_state():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
        
    cursor = conn.cursor(dictionary=True)
    try:
        stats = fetch_brain_state_stats(cursor)
        insights = generate_brain_cognitive_insight(cursor)
        recent_logs = fetch_recent_neural_logs(limit=10)
        conn.close()
        return jsonify({
            'status': 'success',
            'stats': stats,
            'insights': insights,
            'logs': recent_logs,
            'timestamp': datetime.datetime.now().isoformat()
        })
    except Exception as e:
        if conn: conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/intelligence/brain-state/trigger', methods=['POST'])
def trigger_brain_state_evolution():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    # Run evolution in background thread
    schedule_brain_evolution(None)
    return jsonify({'status': 'success', 'message': 'Evolving brain core in real-time...'})



@app.route('/admin/intelligence/twin')
def admin_intelligence_twin():
    return render_template('admin/intelligence/business_twin.html')

@app.route('/admin/intelligence/forecasting')
def admin_intelligence_forecasting():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    if not session.get('forecasting_unlocked'):
        return render_template('admin/intelligence/forecasting_lock.html')
    return render_template('admin/intelligence/forecasting.html')


@app.route('/admin/intelligence/forecasting/lock')
def admin_intelligence_forecasting_lock_action():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    session.pop('forecasting_unlocked', None)
    return redirect(url_for('admin_intelligence_forecasting'))


@app.route('/api/admin/intelligence/forecasting/verify-lock', methods=['POST'])
def api_forecasting_verify_lock():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    data = request.json or {}
    password = data.get('password', '').strip()
    stored_password = os.environ.get("FORECASTING_PASSWORD", "1234")
    
    if password == stored_password:
        session['forecasting_unlocked'] = True
        return jsonify({'status': 'success', 'message': 'Unlocked'})
    else:
        return jsonify({'status': 'error', 'message': 'Incorrect PIN'}), 400


@app.route('/api/admin/intelligence/forecasting/change-password', methods=['POST'])
def api_forecasting_change_password():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    data = request.json or {}
    current_password = data.get('current_password', '').strip()
    new_password = data.get('new_password', '').strip()
    
    if not new_password:
        return jsonify({'status': 'error', 'message': 'New PIN cannot be empty'}), 400
        
    stored_password = os.environ.get("FORECASTING_PASSWORD", "1234")
    
    if current_password != stored_password:
        return jsonify({'status': 'error', 'message': 'Current PIN is incorrect'}), 400
        
    try:
        update_env_variable("FORECASTING_PASSWORD", new_password)
        return jsonify({'status': 'success', 'message': 'PIN updated successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/intelligence/forecasting/data')
def api_intelligence_forecasting_data():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    import math
    scenario = request.args.get('scenario', 'auto').lower()
    
    # Define scaling factors per scenario & category
    factors = {
        'normal': {},
        'festival': {'spices': 1.6, 'oils': 1.8, 'tea': 1.3, 'beverages': 1.5, 'sweets': 2.0},
        'monsoon': {'tea': 1.5, 'spices': 1.3, 'herbs': 1.4},
        'summer': {'beverages': 1.6, 'oils': 1.2}
    }
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500
        
    try:
        cursor = conn.cursor(dictionary=True)
        
        # 1. AI Autopilot Scenario Auto-Detection
        detected_scenario = 'normal'
        auto_reason = 'AI Autopilot: Default baseline modeling (normal demand) active.'
        today = datetime.date.today()
        
        # Fetch holidays from DB
        cursor.execute("SELECT name, date FROM holidays")
        holiday_rows = cursor.fetchall()
        
        upcoming_holiday = None
        days_until_holiday = 999
        for h in holiday_rows:
            h_date = h['date']
            if isinstance(h_date, str):
                try:
                    h_date = datetime.datetime.strptime(h_date, '%Y-%m-%d').date()
                except:
                    continue
            diff = (h_date - today).days
            if 0 <= diff <= 15:
                if diff < days_until_holiday:
                    days_until_holiday = diff
                    upcoming_holiday = h['name']
                    
        if upcoming_holiday:
            detected_scenario = 'festival'
            auto_reason = f"AI Detected: Upcoming Festival Season ({upcoming_holiday} is in {days_until_holiday} days). Pre-emptively scaling category demands."
        else:
            is_summer = (today.month == 5) or (today.month == 4 and today.day >= 15) or (today.month == 6 and today.day <= 15)
            if is_summer:
                detected_scenario = 'summer'
                auto_reason = "AI Detected: Summer Peak Season active. Beverages (+60%) and Oils (+20%) scaled automatically."
            elif today.month == 7:
                detected_scenario = 'monsoon'
                auto_reason = "AI Detected: Monsoon Season active. Hot Tea (+50%) and warming Spices (+30%) scaled automatically."
                
        # Determine active scenario and factors
        active_scenario = detected_scenario if scenario == 'auto' else scenario
        scenario_factors = factors.get(active_scenario, {})
        default_factor = 1.2 if active_scenario == 'festival' else (1.1 if active_scenario in ('monsoon', 'summer') else 1.0)
        
        # 2. Fetch historical memory bank multipliers for the current month
        hist_multipliers = {}
        try:
            cursor.execute("""
                SELECT category, AVG(multiplier) as avg_mult
                FROM seasonal_history
                WHERE month = %s
                GROUP BY category
            """, (today.month,))
            hist_rows = cursor.fetchall()
            hist_multipliers = {r['category'].lower().strip(): float(r['avg_mult']) for r in hist_rows}
        except Exception as e:
            print(f"Failed to fetch historical multipliers: {e}")
            
        # 3. Fetch products and check sales quantities from active bills (last 30 days)
        query = """
            SELECT 
                p.barcode,
                p.name,
                p.category,
                p.price,
                p.current_stock,
                p.min_threshold,
                p.unit,
                COALESCE(SUM(bi.qty), 0) as sales_qty_30d
            FROM products p
            LEFT JOIN bill_items bi ON p.name = bi.product_name
            LEFT JOIN bills b ON bi.bill_id = b.id AND b.status != 'Cancelled' AND b.bill_date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            GROUP BY p.barcode, p.name, p.category, p.price, p.current_stock, p.min_threshold, p.unit
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        
        forecast_items = []
        purchase_orders = []
        
        for row in rows:
            barcode = row['barcode'] or 'N/A'
            name = row['name']
            category = row['category'] or 'General'
            price = float(row['price'] or 0.0)
            current_stock = float(row['current_stock'] or 0.0)
            min_threshold = float(row['min_threshold'] or 10.0)
            unit = row['unit'] or 'PCS'
            sales_qty_30d = float(row['sales_qty_30d'] or 0.0)
            
            # Daily sales rate over the last 30 days
            daily_sales_rate = sales_qty_30d / 30.0
            
            # Apply scenario multiplier based on product category
            cat_key = category.lower().strip()
            multiplier = default_factor
            
            # Use historical trend overlay if Auto-Detect is active and trend exists
            has_history = False
            if scenario == 'auto' and cat_key in hist_multipliers:
                multiplier = hist_multipliers[cat_key]
                has_history = True
            else:
                for k, val in scenario_factors.items():
                    if k in cat_key:
                        multiplier = val
                        break
                        
            forecasted_daily_rate = daily_sales_rate * multiplier
            
            # Remaining days of stock
            if forecasted_daily_rate > 0:
                remaining_days = current_stock / forecasted_daily_rate
            else:
                remaining_days = 999.0
                
            # Risk status based on remaining days of stock
            if remaining_days <= 7:
                status = 'Urgent'
                status_color = '#ef4444' # Red
            elif remaining_days <= 15:
                status = 'Watchlist'
                status_color = '#f59e0b' # Orange
            else:
                status = 'Safe'
                status_color = '#10b981' # Green
                
            # Run-out date prediction
            if remaining_days < 365:
                runout_date = (datetime.date.today() + datetime.timedelta(days=int(remaining_days))).isoformat()
            else:
                runout_date = 'Never'
                
            item = {
                'barcode': barcode,
                'name': name,
                'category': category,
                'price': price,
                'current_stock': current_stock,
                'min_threshold': min_threshold,
                'unit': unit,
                'daily_sales_rate': round(daily_sales_rate, 3),
                'multiplier': multiplier,
                'forecasted_daily_rate': round(forecasted_daily_rate, 3),
                'remaining_days': round(remaining_days, 1) if remaining_days < 999 else 'Infinite',
                'status': status,
                'status_color': status_color,
                'runout_date': runout_date,
                'has_history': has_history,
                'auto_detected': scenario == 'auto'
            }
            forecast_items.append(item)
            
            # Reorder PO recommendations
            if remaining_days <= 15:
                # Cover next 30 days of sales
                target_stock = forecasted_daily_rate * 30.0
                reorder_qty = target_stock - current_stock
                min_reorder = max(10.0, min_threshold)
                if reorder_qty < min_reorder:
                    reorder_qty = min_reorder
                    
                reorder_qty = int(math.ceil(reorder_qty))
                estimated_unit_cost = price * 0.75 # Assume 25% margin
                total_cost = reorder_qty * estimated_unit_cost
                
                purchase_orders.append({
                    'barcode': barcode,
                    'name': name,
                    'category': category,
                    'current_stock': current_stock,
                    'suggested_qty': reorder_qty,
                    'unit': unit,
                    'unit_cost': round(estimated_unit_cost, 2),
                    'total_cost': round(total_cost, 2)
                })
                
        status_priority = {'Urgent': 0, 'Watchlist': 1, 'Safe': 2}
        forecast_items.sort(key=lambda x: (status_priority.get(x['status'], 2), x['remaining_days'] if isinstance(x['remaining_days'], (int, float)) else 999))
        purchase_orders.sort(key=lambda x: x['total_cost'], reverse=True)
        
        return jsonify({
            'status': 'success',
            'scenario': active_scenario,
            'detected_scenario': detected_scenario,
            'auto_reason': auto_reason,
            'data': forecast_items,
            'purchase_orders': purchase_orders,
            'timestamp': datetime.datetime.now().isoformat()
        })
        
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/intelligence/forecasting/holidays', methods=['GET', 'POST'])
def api_forecasting_holidays():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        if request.method == 'GET':
            cursor.execute("SELECT id, name, date FROM holidays ORDER BY date ASC")
            rows = cursor.fetchall()
            for r in rows:
                if hasattr(r['date'], 'isoformat'):
                    r['date'] = r['date'].isoformat()
            conn.close()
            return jsonify({'status': 'success', 'data': rows})
            
        elif request.method == 'POST':
            data = request.json or {}
            action = data.get('action', 'save')
            holiday_id = data.get('id')
            name = data.get('name', '').strip()
            date_val = data.get('date', '').strip()
            
            if action == 'delete':
                if not holiday_id:
                    conn.close()
                    return jsonify({'status': 'error', 'message': 'Holiday ID is required for deletion'}), 400
                cursor.execute("DELETE FROM holidays WHERE id = %s", (holiday_id,))
                conn.commit()
                conn.close()
                return jsonify({'status': 'success', 'message': 'Holiday deleted successfully.'})
                
            else: # save
                if not name or not date_val:
                    conn.close()
                    return jsonify({'status': 'error', 'message': 'Name and date are required'}), 400
                
                if holiday_id:
                    cursor.execute("""
                        UPDATE holidays SET name = %s, date = %s WHERE id = %s
                    """, (name, date_val, holiday_id))
                else:
                    cursor.execute("DELETE FROM holidays WHERE name = %s", (name,))
                    cursor.execute("""
                        INSERT INTO holidays (name, date) VALUES (%s, %s)
                    """, (name, date_val))
                conn.commit()
                conn.close()
                return jsonify({'status': 'success', 'message': 'Holiday saved successfully.'})
                
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/intelligence/forecasting/holidays/autopilot', methods=['POST'])
def api_forecasting_holidays_autopilot():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    conn = get_db_connection()
    if not conn:
        return jsonify({'status': 'error', 'message': 'Database connection failed'}), 500

    try:
        import datetime
        import requests
        import re

        current_year = datetime.date.today().year
        years_to_sync = [current_year, current_year + 1]
        
        url = "https://calendar.google.com/calendar/ical/en.indian%23holiday%40group.v.calendar.google.com/public/basic.ics"
        response = requests.get(url, timeout=15)
        
        if response.status_code != 200:
            conn.close()
            return jsonify({'status': 'error', 'message': f'Failed to download public holiday calendar (HTTP {response.status_code})'}), 502
            
        content = response.text
        raw_events = re.findall(r'BEGIN:VEVENT.*?END:VEVENT', content, re.DOTALL)
        
        synced_count = 0
        cursor = conn.cursor(dictionary=True)
        
        for event_str in raw_events:
            summary_match = re.search(r'SUMMARY:(.*)', event_str)
            dtstart_match = re.search(r'DTSTART;VALUE=DATE:(\d{8})', event_str)
            if not dtstart_match:
                dtstart_match = re.search(r'DTSTART:(\d{8})', event_str)
                
            if summary_match and dtstart_match:
                clean_name = summary_match.group(1).strip().replace('\\\\', '').replace('\\,', ',')
                dt_str = dtstart_match.group(1).strip()
                try:
                    event_date = datetime.datetime.strptime(dt_str, "%Y%m%d").date()
                except Exception:
                    continue
                
                if event_date.year in years_to_sync:
                    name_with_year = f"{clean_name} {event_date.year}"
                    date_val = event_date.strftime('%Y-%m-%d')
                    
                    # Upsert check using the unique name (e.g., "Pongal 2026")
                    cursor.execute("SELECT id FROM holidays WHERE name = %s", (name_with_year,))
                    existing = cursor.fetchone()
                    if existing:
                        cursor.execute("UPDATE holidays SET date = %s WHERE id = %s", (date_val, existing['id']))
                    else:
                        cursor.execute("INSERT INTO holidays (name, date) VALUES (%s, %s)", (name_with_year, date_val))
                    synced_count += 1
                    
        conn.commit()
        conn.close()
        return jsonify({
            'status': 'success',
            'synced_count': synced_count,
            'years': years_to_sync
        })
        
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500


def update_env_variable(key, value):
    try:
        os.environ[key] = value
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        env_path = os.path.join(base_dir, ".env")
        
        env_lines = []
        updated = False
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line_stripped = line.strip()
                    if line_stripped.startswith(f"{key}="):
                        env_lines.append(f"{key}={value}\n")
                        updated = True
                    else:
                        env_lines.append(line)
        if not updated:
            env_lines.append(f"{key}={value}\n")
            
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(env_lines)
    except Exception as e:
        print(f"Failed to write to .env file: {e}")
        raise e


@app.route('/api/admin/config/groq-key', methods=['GET', 'POST'])
def api_admin_groq_key():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    if request.method == 'GET':
        groq_api_key = os.environ.get("GROQ_API_KEY", "")
        usage_info = {
            'status': 'Inactive',
            'remaining_requests': 'N/A',
            'limit_requests': 'N/A',
            'remaining_tokens': 'N/A',
            'limit_tokens': 'N/A',
            'error_message': None
        }
        
        if groq_api_key:
            import requests
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1
                    },
                    headers={"Authorization": f"Bearer {groq_api_key}"},
                    timeout=5
                )
                if r.status_code == 200:
                    usage_info['status'] = 'Active'
                    usage_info['remaining_requests'] = r.headers.get('x-ratelimit-remaining-requests', 'N/A')
                    usage_info['limit_requests'] = r.headers.get('x-ratelimit-limit-requests', 'N/A')
                    usage_info['remaining_tokens'] = r.headers.get('x-ratelimit-remaining-tokens', 'N/A')
                    usage_info['limit_tokens'] = r.headers.get('x-ratelimit-limit-tokens', 'N/A')
                else:
                    usage_info['status'] = 'Error'
                    try:
                        err_json = r.json()
                        usage_info['error_message'] = err_json.get('error', {}).get('message', f"HTTP {r.status_code}")
                    except Exception:
                        usage_info['error_message'] = f"HTTP {r.status_code}"
            except Exception as e:
                usage_info['status'] = 'Connection Error'
                usage_info['error_message'] = str(e)
                
        return jsonify({
            'status': 'success',
            'groq_api_key': groq_api_key,
            'usage': usage_info
        })
        
    elif request.method == 'POST':
        data = request.json or {}
        new_key = data.get('groq_api_key', '').strip()
        
        if not new_key:
            return jsonify({'status': 'error', 'message': 'API Key cannot be empty.'}), 400
            
        if not new_key.startswith('gsk_'):
            return jsonify({'status': 'error', 'message': 'Invalid key format. Groq API keys should start with gsk_'}), 400
            
        try:
            update_env_variable("GROQ_API_KEY", new_key)
            return jsonify({'status': 'success', 'message': 'API Key updated successfully!'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/admin/intelligence/share-chat', methods=['POST'])
def share_chat():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    data = request.json or {}
    recipient_email = data.get('email', '').strip()
    history = data.get('history', [])

    if not recipient_email:
        return jsonify({'status': 'error', 'message': 'Email address is required'}), 400
    if not history:
        return jsonify({'status': 'error', 'message': 'Chat history is empty'}), 400

    try:
        from fpdf import FPDF
        import re
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders

        # Clean HTML function
        def clean_html(text):
            # Replace tags with spaces or newlines where appropriate
            text = re.sub(r'</p>|<br\s*/?>|</div>|</tr>', '\n', text)
            # Remove all remaining HTML tags
            clean = re.compile('<.*?>')
            text = clean.sub('', text)
            # Unescape basic HTML entities
            text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&nbsp;', ' ')
            text = text.replace('Rs.', 'Rs. ').replace('\u20B9', 'Rs. ')
            # Strip multiple newlines
            text = re.sub(r'\n\n+', '\n', text)
            return text.strip()

        # Build FPDF Class with Header/Footer to look professional
        class ChatPDF(FPDF):
            def header(self):
                self.set_font("Helvetica", "B", 10)
                self.set_text_color(128, 128, 128)
                self.cell(0, 10, "MaplePro AI Assistant - Chat Report", border=0, align="L")
                self.cell(0, 10, datetime.date.today().strftime("%Y-%m-%d"), border=0, align="R")
                self.ln(10)
                self.line(10, 18, 200, 18)
                self.ln(5)

            def footer(self):
                self.set_y(-15)
                self.set_font("Helvetica", "I", 8)
                self.set_text_color(128, 128, 128)
                self.cell(0, 10, f"Page {self.page_no()}", align="C")

        # Create PDF
        pdf = ChatPDF()
        pdf.add_page()
        
        # Document Title
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(30, 41, 59) # Slate 800
        pdf.cell(0, 12, "AI Business Twin Conversation Log", align="L")
        pdf.ln(12)
        pdf.ln(5)

        # Iterate history and print paragraphs
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            clean_content = clean_html(content)
            if not clean_content:
                continue

            # Section Header for role
            pdf.set_font("Helvetica", "B", 10)
            if role == "user":
                pdf.set_text_color(79, 70, 229) # Indigo 600
                pdf.cell(0, 6, "User Query:")
                pdf.ln(6)
            else:
                pdf.set_text_color(13, 148, 136) # Teal 600
                pdf.cell(0, 6, "AI Copilot Response:")
                pdf.ln(6)

            # Paragraph Text
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(51, 65, 85) # Slate 700
            
            clean_content_latin = clean_content.encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 5, text=clean_content_latin)
            pdf.ln(4)

        pdf_dir = os.path.join(base_dir, "temp")
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_path = os.path.join(pdf_dir, "chat_transcript.pdf")
        pdf.output(pdf_path)

        # Email Sending
        sender_email = "maplepro2323@gmail.com"
        sender_password = "vkah llvc mduj yfze"

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = f"MaplePro AI Assistant Report - {datetime.date.today().strftime('%Y-%m-%d')}"

        body = (
            "Hello,\n\n"
            "Please find attached the PDF report containing the conversation transcript "
            "from the MaplePro AI Business Twin Assistant.\n\n"
            "This is an automated system email. Please do not reply directly to this message.\n\n"
            "Best Regards,\n"
            "MaplePro Systems"
        )
        msg.attach(MIMEText(body, 'plain'))

        # Read PDF and attach
        with open(pdf_path, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())

        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f"attachment; filename={os.path.basename(pdf_path)}",
        )
        msg.attach(part)

        # SMTP Connection
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()

        # Clean up file
        try:
            os.remove(pdf_path)
        except:
            pass

        return jsonify({'status': 'success', 'message': 'PDF report sent to your email successfully.'})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': f'Failed to generate or send PDF: {str(e)}'}), 500

@app.route('/api/admin/intelligence/forecasting/email', methods=['POST'])
def api_forecasting_email():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    data = request.json or {}
    recipient_email = data.get('email', '').strip()
    subject = data.get('subject', '').strip()
    body = data.get('body', '').strip()

    if not recipient_email:
        return jsonify({'status': 'error', 'message': 'Recipient email address is required'}), 400
    if not subject:
        return jsonify({'status': 'error', 'message': 'Subject is required'}), 400
    if not body:
        return jsonify({'status': 'error', 'message': 'Email content body is required'}), 400

    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        sender_email = "maplepro2323@gmail.com"
        sender_password = "vkah llvc mduj yfze"

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject

        # Support HTML body format
        msg.attach(MIMEText(body, 'html'))

        # SMTP Connection
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()

        return jsonify({'status': 'success', 'message': 'Purchase order emailed successfully.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/intelligence/twin/ask', methods=['POST'])
def api_twin_ask():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    import requests
    import json
    import re
    
    data = request.json or {}
    user_query = data.get('query', '').strip()
    chat_history = data.get('history', [])
    if not user_query:
        return jsonify({'status': 'error', 'message': 'Query is empty'}), 400

    # Table schema description for the SQL generator
    schema_info = """
    We have the following tables in our active database:
    
    1. products (tracks products in stock):
       - id (int, primary key)
       - barcode (varchar, product code/code)
       - name (varchar, product name)
       - category (varchar, e.g. 'Dairy', 'Snacks')
       - price (decimal, retail price)
       - current_stock (decimal, active count in stock)
       - min_threshold (decimal, low stock alert level)
       - unit (varchar, e.g. 'PCS', 'KG')
       - expiry_date (date)
       - bizz (decimal, loyalty reward percentage)
       
    2. bills (invoices generated):
       - id (int, primary key)
       - invoice_no (varchar)
       - bill_date (datetime/timestamp, when the bill was printed)
       - total_amount (decimal)
       - payment_mode (varchar, e.g. 'CASH', 'UPI', 'CARD')
       - status (varchar, 'PAID', 'Paid', or 'Cancelled')
       - discount (decimal)
       - prev_total (decimal, if cancelled/voided)
       - created_by (varchar, username of the clerk/cashier who made the bill)
       
    3. bill_items (individual product items inside invoices, linked by bill_id):
       - id (int, primary key)
       - bill_id (int, references bills.id)
       - product_code (varchar, references products.barcode)
       - product_name (varchar, references products.name)
       - qty (int, quantity sold)
       - rate (decimal, selling price per unit)
       - amount (decimal, total for this line item, i.e. qty * rate)
       - bizz_percent (decimal)
       - bizz_amount (decimal)
       
    4. returns_log (logs of items returned or bills voided):
       - id (int, primary key)
       - bill_id (int)
       - product_name (varchar)
       - qty (decimal, returned qty)
       - amount (decimal, refund amount)
       - reason (varchar, e.g. 'Damaged', 'Billing mistake')
       - returned_at (timestamp, transaction date)
       - created_by (varchar, clerk who did the refund)
       - status (varchar)
       - action (varchar, 'restock' or 'scrap')
       
    5. expenses (daily operational business expenses):
       - id (int, primary key)
       - category (varchar)
       - description (text)
       - amount (decimal)
       - expense_date (datetime/timestamp)
       - expense_group (varchar)
    """

    groq_api_key = os.environ.get("GROQ_API_KEY", "")
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }

    # Step 1: LLM decides if it needs a SQL query to answer the user query, and generates it.
    sql_generation_prompt = (
        "You are a database operations expert for MaplePro Billing Software.\n"
        "Your task is to analyze the user's natural language question and write a safe, clean SQL SELECT statement to fetch the required data.\n"
        "If the question does not require database records (e.g. a greeting or general help), answer with the word 'NONE'.\n"
        "Rules:\n"
        "1. You MUST ONLY write a single SELECT statement. No insert, update, delete or other DDL statements.\n"
        "2. Do not explain the SQL or provide any text other than the SQL query itself or the word 'NONE'.\n"
        "3. Ensure column names exist in the schema provided.\n"
        "4. If filtering by date, remember that bill_date is datetime/timestamp, so use DATE(bill_date) to match dates like CURDATE() or CURRENT_DATE.\n"
        "5. Output only the query. No formatting, no code blocks, no backticks.\n"
        "6. STRING LITERALS: You MUST use single quotes (') for all string literals (e.g., WHERE status != 'Cancelled' or WHERE payment_mode = 'CASH'). Never use double quotes (\") for strings, as PostgreSQL/MySQL treats them as column names.\n"
        "7. JOINING RULE: If you need to join products and bill_items, always join on name ('ON products.name = bill_items.product_name'). If you just need the list of products sold, query bill_items.product_name directly without joining products at all!\n"
        "8. BILLS RULE: Always filter active bills using 'status != \'Cancelled\'' unless the user asks specifically for voids or cancelled invoices.\n"
        f"Schema Info:\n{schema_info}"
    )

    models_to_try = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gemma2-9b-it"]
    sql_query = None
    
    for model in models_to_try:
        try:
            messages = [{"role": "system", "content": sql_generation_prompt}]
            for turn in chat_history[-6:]:
                messages.append({
                    "role": turn.get("role", "user"),
                    "content": turn.get("content", "").strip()
                })
            messages.append({"role": "user", "content": user_query})
            
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 300
            }
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=10)
            if r.status_code == 200:
                raw_sql = r.json()["choices"][0]["message"]["content"].strip()
                # Clean up markdown formatting if the model put backticks
                raw_sql = raw_sql.replace("```sql", "").replace("```", "").strip()
                if raw_sql != 'NONE' and raw_sql:
                    sql_query = raw_sql
                break
        except Exception:
            pass

    db_context_str = "No database queries executed."
    
    # Step 2: Validate and execute SQL query if generated
    if sql_query:
        # Strip comments
        cleaned_sql = re.sub(r'--.*$', '', sql_query, flags=re.MULTILINE)
        cleaned_sql = cleaned_sql.strip()
        
        # Word-by-word security validation
        q_upper = cleaned_sql.upper()
        words = re.findall(r'\b\w+\b', q_upper)
        
        forbidden = [
            'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', 
            'TRUNCATE', 'REPLACE', 'GRANT', 'REVOKE', 'RENAME', 'EXECUTE',
            'LOAD_FILE', 'OUTFILE', 'DUMPFILE', 'USERS', 'AUDIT_LOGS'
        ]
        
        is_safe = cleaned_sql.lower().startswith('select') and not any(w in forbidden for w in words)
        
        if is_safe:
            # Append LIMIT 100 to protect memory if not present
            if 'LIMIT' not in q_upper:
                cleaned_sql = cleaned_sql.rstrip(';') + " LIMIT 100;"
                
            # Pre-compile: Convert double quoted string values to single quotes for SQL compatibility (e.g. status != "Cancelled" -> status != 'Cancelled')
            cleaned_sql = re.sub(r'"([^"]*)"', r"'\1'", cleaned_sql)
            
            conn = get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute(cleaned_sql)
                    rows = cursor.fetchall()
                    
                    # Sanitization/Masking layer for LLM data privacy
                    secure_rows = []
                    sensitive_cols = {
                        'password_hash', 'password', 'email', 'phone', 'phone_number',
                        'client_request_id', 'user_id',
                        'raw_app_meta_data', 'raw_user_meta_data', 'encrypted_password'
                    }
                    import re
                    email_pat = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
                    phone_pat = re.compile(r'\b\d{10}\b|\b\d{3}[-.\s]??\d{3}[-.\s]??\d{4}\b')
                    for r in rows:
                        if isinstance(r, dict):
                            new_r = {}
                            for k, v in r.items():
                                if k.lower() in sensitive_cols:
                                    new_r[k] = "[REDACTED_SECURE]"
                                elif isinstance(v, str):
                                    v = email_pat.sub("[EMAIL_MASKED]", v)
                                    v = phone_pat.sub("[PHONE_MASKED]", v)
                                    new_r[k] = v
                                else:
                                    new_r[k] = v
                            secure_rows.append(new_r)
                        else:
                            secure_rows.append(r)

                    db_context_str = f"SQL QUERY EXECUTED: {cleaned_sql}\nRESULTS:\n{json.dumps(secure_rows, default=str, indent=2)}"
                    conn.close()
                except Exception as e:
                    if conn: conn.close()
                    db_context_str = f"SQL QUERY: {cleaned_sql}\nEXECUTION ERROR: {str(e)}"
        else:
            db_context_str = f"SQL QUERY REJECTED FOR SECURITY: {sql_query}"

    # Step 3: Call LLM to format final rich natural language answer
    today_str = datetime.date.today().isoformat()
    system_prompt = (
        "You are the 'AI Digital Twin' for Sagar Nilgiri Products (powered by MaplePro Billing Software).\n"
        "Your role is to analyze real-time business data and answer the owner's queries with clarity, precision, and actionable insight.\n"
        "Tone: Professional, analytical, concise. No filler phrases.\n"
        "Audience: A business owner — not a developer or data analyst.\n\n"
        "RULES:\n"
        "1. FORBIDDEN LANGUAGE:\n"
        "   NEVER mention: SQL, queries, database, tables, columns, schemas, technical error messages or stack traces, or words like 'fetched', 'executed', 'queried', 'record set'.\n"
        "   ALWAYS use natural business language instead (e.g., 'Based on your sales data today...', 'Your records show...', etc.).\n\n"
        "2. DATA RESULT STATES:\n"
        "   - If no records are found, say: 'No [sales/products/invoices] were found for [period/filter].' Do NOT guess or extrapolate.\n"
        "   - If there is an error, say: 'I was unable to retrieve that information. Please try again.' Do NOT expose any technical details.\n\n"
        "3. CURRENCY RULE:\n"
        "   All monetary values MUST strictly use the Indian Rupee symbol (\u20B9) and be formatted using Indian numbering style (e.g., \u20B9750.00, \u20B92,500.00, \u20B91,50,000.00). NEVER use '$', 'USD', 'INR' (as text), or Western comma formatting for lakh/crore figures.\n\n"
        "4. HTML TABLE RULES:\n"
        "   Any structured or comparative data with 2 or more rows MUST be rendered as an HTML table. Never use plain-text lists for structured data.\n"
        "   If the result has more than 20 rows, show the top 10 by value (or most recent), add a totals/summary row, and note: 'Showing top 10 of [N] records.'\n"
        "   Table styling:\n"
        "   <table style=\"width:100%; border-collapse:collapse; font-size:13px;\">\n"
        "     <thead>\n"
        "       <tr style=\"background:rgba(255,255,255,0.04); text-align:left;\">\n"
        "         <th style=\"padding:8px 12px; font-weight:500; border-bottom:1px solid rgba(255,255,255,0.08);\">Column Name</th>\n"
        "       </tr>\n"
        "     </thead>\n"
        "     <tbody>\n"
        "       <tr style=\"border-bottom:0.5px solid rgba(255,255,255,0.06);\">\n"
        "         <td style=\"padding:8px 12px;\">Value</td>\n"
        "       </tr>\n"
        "     </tbody>\n"
        "   </table>\n\n"
        "5. STATUS BADGES & PROGRESS BARS:\n"
        "   - Green badge (Active, Paid, In Stock): <span style=\"background:rgba(16,185,129,0.15);color:#059669;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:700;border:1px solid rgba(16,185,129,0.3);\">Active</span>\n"
        "   - Orange badge (Pending, Low Stock, Partial): <span style=\"background:rgba(245,158,11,0.15);color:#d97706;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:700;border:1px solid rgba(245,158,11,0.3);\">Pending</span>\n"
        "   - Red badge (Cancelled, Overdue, Out of Stock): <span style=\"background:rgba(239,68,68,0.15);color:#dc2626;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:700;border:1px solid rgba(239,68,68,0.3);\">Cancelled</span>\n"
        "   - Progress bar: <div style=\"background:rgba(255,255,255,0.08);height:6px;border-radius:10px;overflow:hidden;width:80px;display:inline-block;vertical-align:middle;margin-right:6px;\"><div style=\"background:#10b981;width:WIDTH_PERCENT;height:100%;border-radius:10px;\"></div></div> WIDTH_PERCENT (Replace WIDTH_PERCENT with computed value, e.g. 63%)\n\n"
        "6. RESPONSE LENGTH & STRUCTURE:\n"
        "   - Simple queries (single number, quick lookup): 1-2 sentence answer under 60 words.\n"
        "   - Analytical queries (sales trends, stock velocity, top products, comparisons): 1-sentence summary of the key finding, followed by HTML table, and ending with a 1-sentence business insight. Word cap: under 250 words + table.\n"
        "   - Output format: HTML only. Use <p>, <strong>, and <em> for prose. Do NOT use Markdown (*, **, #, backticks).\n\n"
        "7. ADMIN / OWNER RULE:\n"
        "   The 'admin' user is the store administrator/owner account used only for viewing data, running system tests, and reports. It is NOT a cashier counter or sales counter, and should not be treated as a normal counter. When reporting counter performance or listing cashier sales, ignore sales under 'admin' or state clearly that 'admin' is for administrator/testing only.\n\n"
        "8. NO HALLUCINATION RULE:\n"
        "   Do NOT guess, estimate, or invent any numbers, dates, or product names. Your response must be grounded 100% in the live data context provided.\n\n"
        f"Today's Date: {today_str}\n"
        f"--- LIVE DATA CONTEXT ---\n"
        f"{db_context_str}\n"
    )

    ai_response = None
    last_error = ""

    messages_final = [{"role": "system", "content": system_prompt}]
    for turn in chat_history[-6:]:
        messages_final.append({
            "role": turn.get("role", "user"),
            "content": turn.get("content", "").strip()
        })
    messages_final.append({"role": "user", "content": user_query})

    for model in models_to_try:
        payload = {
            "model": model,
            "messages": messages_final,
            "temperature": 0.4,
            "max_tokens": 1024
        }
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=15)
            if r.status_code == 200:
                resp_data = r.json()
                ai_response = resp_data["choices"][0]["message"]["content"]
                break
            else:
                last_error = f"HTTP {r.status_code}: {r.text}"
        except Exception as e:
            last_error = str(e)

    if ai_response:
        return jsonify({'status': 'success', 'answer': ai_response})
    else:
        return jsonify({
            'status': 'error', 
            'message': f"Failed to generate Business Twin answer: {last_error}"
        }), 500



@app.route('/admin/maintenance/health')
def admin_maintenance_health():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('admin/maintenance/health.html')

@app.route('/api/admin/maintenance/status')
def api_maintenance_status():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        
    is_local_host = Config.MYSQL_HOST in ('127.0.0.1', 'localhost')
    if is_local_host:
        mysql_alive = is_process_running("mysqld.exe") and is_port_open(Config.MYSQL_PORT, Config.MYSQL_HOST)
    else:
        mysql_alive = is_port_open(Config.MYSQL_PORT, Config.MYSQL_HOST)
    
    cloud_alive = False
        
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        current_ip = s.getsockname()[0]
        s.close()
    except:
        current_ip = "127.0.0.1"
        
    return jsonify({
        'status': 'success',
        'telemetry': {
            'mysql': 'ONLINE' if mysql_alive else 'OFFLINE',
            'cloud_db': 'ONLINE' if cloud_alive else 'OFFLINE',
            'local_ip': current_ip,
            'waitress': 'ONLINE',
            'printer': 'ONLINE' if is_port_open(9100, "127.0.0.1", 0.5) else 'ONLINE (USB Virtual Mode)'
        }
    })

@app.route('/api/admin/maintenance/metrics')
def api_maintenance_metrics():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    return jsonify({
        'status': 'success',
        'history': MYSQL_HEALTH_HISTORY,
        'risk': MYSQL_DOWNTIME_RISK,
        'simulated_delay': SIMULATED_MYSQL_DELAY,
        'simulated_failures': SIMULATED_MYSQL_FAILURES
    })

@app.route('/api/admin/maintenance/simulate', methods=['POST'])
def api_maintenance_simulate():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        
    data = request.json or {}
    global SIMULATED_MYSQL_DELAY, SIMULATED_MYSQL_FAILURES
    
    if 'delay' in data:
        SIMULATED_MYSQL_DELAY = float(data['delay'])
    if 'failures' in data:
        SIMULATED_MYSQL_FAILURES = bool(data['failures'])
        
    if SIMULATED_MYSQL_FAILURES:
        log_healing_event("MySQL Database", "FAULT", "Simulated database connection drops activated by administrator.", "Failover preparing; monitoring connection recovery.")
    elif 'failures' in data and not SIMULATED_MYSQL_FAILURES:
        log_healing_event("MySQL Database", "HEALED", "Simulated database connection drops deactivated by administrator.", "Connection re-established and healthy.")
        
    return jsonify({
        'status': 'success',
        'message': 'Simulation state updated successfully.',
        'simulated_delay': SIMULATED_MYSQL_DELAY,
        'simulated_failures': SIMULATED_MYSQL_FAILURES
    })

@app.route('/api/admin/maintenance/logs')
def api_maintenance_logs():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "self_healing.db")
    logs = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM healing_logs ORDER BY id DESC LIMIT 50")
        rows = cursor.fetchall()
        for r in rows:
            logs.append(dict(r))
        conn.close()
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
        
    return jsonify({'status': 'success', 'logs': logs})

@app.route('/api/admin/maintenance/recover', methods=['POST'])
def api_maintenance_recover():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    return jsonify({'status': 'success', 'message': 'Autopilot is currently in development simulation mode. Laragon auto-launch is disabled.'})

@app.route('/api/admin/maintenance/ai-diagnose/<int:log_id>', methods=['POST'])
def api_maintenance_ai_diagnose(log_id):
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "self_healing.db")
    log_entry = None
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM healing_logs WHERE id = ?", (log_id,))
        row = cursor.fetchone()
        if row:
            log_entry = dict(row)
        conn.close()
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
        
    if not log_entry:
        return jsonify({'status': 'error', 'message': 'Log entry not found'}), 444
        
    # If already cached, return the cache
    if log_entry.get('ai_diagnosis') and log_entry['ai_diagnosis'] != "AI Diagnosis pending selection..." and log_entry['ai_diagnosis'] != "Diagnosis pending trigger...":
        return jsonify({'status': 'success', 'diagnosis': log_entry['ai_diagnosis']})
        
    # Generate new AI Diagnosis using Groq
    import requests
    groq_api_key = os.environ.get("GROQ_API_KEY", "")
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }
    
    prompt = (
        "You are 'IT Autopilot AI Specialist' for MaplePro Billing Systems.\n"
        "Analyze this system incident log, explain what it means in clean, friendly terms, "
        "reassure the owner that autopilot resolved or is handling it, and offer a simple advisory action.\n"
        "Formatting: Output your diagnosis in clean, modern HTML paragraphs (<p>), highlights, and alerts. "
        "Keep it concise, supportive, and extremely clear. Do not write markdown, code blocks, or backticks.\n"
        f"Incident Details:\n"
        f"- Service: {log_entry['service']}\n"
        f"- State: {log_entry['status']}\n"
        f"- Message: {log_entry['error_msg']}\n"
        f"- Action Taken: {log_entry['action_taken']}\n"
    )
    
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are a professional IT recovery assistant. Answer using clean inline-styled HTML blocks only."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 500
    }
    
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=12)
        if r.status_code == 200:
            diagnosis_html = r.json()["choices"][0]["message"]["content"].strip()
            
            # Cache the diagnosis in SQLite
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE healing_logs SET ai_diagnosis = ? WHERE id = ?", (diagnosis_html, log_id))
            conn.commit()
            conn.close()
            
            return jsonify({'status': 'success', 'diagnosis': diagnosis_html})
        else:
            return jsonify({'status': 'error', 'message': f'Groq API error: HTTP {r.status_code}'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

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

@app.route('/admin/reports/daily-position')
def admin_reports_daily_position():
    return render_template('admin/reports/daily_position.html')

@app.route('/admin/reports/cancelled-report')
def admin_reports_cancelled_report():
    return render_template('admin/reports/cancelled_report.html')

@app.route('/admin/reports/transfer-report')
def admin_reports_transfer_report():
    return render_template('admin/reports/transfer_report.html')

@app.route('/admin/reports/final-report')
def admin_reports_final_report():
    return render_template('admin/reports/final_report.html')

@app.route('/admin/reports/final-sales-report')
def admin_reports_final_sales_report():
    return render_template('admin/reports/final_sales_report.html')

@app.route('/admin/reports/final-stock')
def admin_reports_final_stock():
    return render_template('admin/reports/final_stock.html')

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
    return render_template('admin/reports/cash_balance.html')

@app.route('/admin/reports/counter-wise')
def admin_reports_counter_wise():
    return render_template('admin/reports/counter_sales.html')

@app.route('/admin/reports/online-sales')
def admin_reports_online_sales():
    return render_template('admin/reports/online_sales.html')

@app.route('/admin/reports/online-sales/reports')
def admin_reports_online_sales_reports():
    return render_template('admin/reports/online_sales_reports.html')

@app.route('/admin/reports/online-sales/invoices')
def admin_reports_online_sales_invoices():
    return render_template('admin/reports/online_sales_invoices.html')

@app.route('/api/reports/online-sales-cloud')
def get_online_sales_cloud_api():
    """
    Fetches online orders - hardcoded to empty list in local-only mode.
    """
    return jsonify([])


@app.route('/admin/returns')
def admin_returns():
    return render_template('admin/returns.html')

@app.route('/admin/network-diagnostics')
def admin_network_diagnostics():
    return render_template('admin/network_diagnostics.html')

@app.route('/api/admin/network/interfaces')
def api_network_interfaces():
    try:
        return jsonify(get_network_interfaces())
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/network/scan')
def api_network_scan():
    try:
        return jsonify(scan_local_network())
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/network/save-label', methods=['POST'])
def api_network_save_label():
    try:
        data = request.json or {}
        ip = data.get('ip')
        label = data.get('label')
        if not ip or not label:
            return jsonify({'status': 'error', 'message': 'IP and label are required'}), 400
        save_device_label(ip, label)
        return jsonify({'status': 'success', 'message': 'Device label saved successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/network/traffic')
def api_network_traffic():
    try:
        return jsonify(get_live_traffic())
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/network/bandwidth')
def api_network_bandwidth():
    try:
        return jsonify(get_bandwidth_by_device())
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/network/port-scan')
def api_network_port_scan():
    try:
        target_ip = request.args.get('ip')
        if not target_ip:
            return jsonify({'status': 'error', 'message': 'Target IP is required'}), 400
        return jsonify(scan_ports(target_ip))
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/network/alerts')
def api_network_alerts():
    try:
        interfaces = get_network_interfaces()
        scanned_ips = get_cached_scan_results()
        health = check_dns_gateway_health()
        alerts = generate_system_alerts(interfaces, scanned_ips, health)
        return jsonify(alerts)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/network/wifi')
def api_network_wifi():
    try:
        return jsonify(get_wifi_info())
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/network/health-check')
def api_network_health_check():
    try:
        return jsonify(check_dns_gateway_health())
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/network/export-report')
def api_network_export_report():
    try:
        interfaces = get_network_interfaces()
        scanned = get_cached_scan_results()
        wifi = get_wifi_info()
        health = check_dns_gateway_health()
        alerts = load_alerts_log()
        
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        report = []
        report.append("=========================================")
        report.append("    MAPLE PRO NETWORK DIAGNOSTIC REPORT   ")
        report.append(f"    Generated: {timestamp}")
        report.append("=========================================\n")
        
        report.append("--- GATEWAY & DNS HEALTH ---")
        for key, val in health.items():
            if not key.endswith("_color") and not key.endswith("_latency"):
                lat = health.get(f"{key}_latency", "N/A")
                report.append(f" {key.upper()}: {val.upper()} ({lat})")
        report.append("")
        
        report.append("--- WI-FI STATISTICS ---")
        if wifi.get("connected"):
            report.append(f" SSID: {wifi.get('ssid')}")
            report.append(f" Band: {wifi.get('band')}")
            report.append(f" Channel: {wifi.get('channel')}")
            report.append(f" Signal: {wifi.get('signal')}% ({wifi.get('signal_dbm')} dBm)")
            report.append(f" Tx/Rx Rates: {wifi.get('rate_tx')} / {wifi.get('rate_rx')}")
        else:
            report.append(" Wi-Fi Status: Disconnected / Not Available")
        report.append("")
        
        report.append("--- NETWORK INTERFACES ---")
        for nic in interfaces:
            report.append(f" Interface: {nic['name']}")
            report.append(f"   IP Address: {nic['ip']}")
            report.append(f"   MAC Address: {nic['mac']}")
            report.append(f"   Status: {nic['status']}")
            report.append(f"   Negotiated Speed: {nic['speed_label']}")
            report.append(f"   Live Traffic (Tx/Rx): {nic['tx_rate']} KB/s / {nic['rx_rate']} KB/s")
            report.append("")
            
        report.append("--- LOCAL IP NETWORK SCAN (LAST CACHED) ---")
        if not scanned:
            report.append(" No scan results available. Run scan from dashboard.")
        else:
            report.append(f" {'IP Address':<16} {'MAC Address':<18} {'VendorPrefix':<15} {'Device Label':<20} {'Status':<8} {'Ping':<8}")
            report.append(" " + "-"*85)
            for dev in scanned:
                status = "ONLINE" if dev['online'] else "OFFLINE"
                ping = f"{dev['latency']} ms" if dev['online'] else "N/A"
                report.append(f" {dev['ip']:<16} {dev['mac']:<18} {dev['vendor']:<15} {dev['label']:<20} {status:<8} {ping:<8}")
        report.append("")
        
        report.append("--- ACTIVE EVENT ALERTS & HISTORY ---")
        if not alerts:
            report.append(" No alerts recorded in history.")
        else:
            for alert in alerts[:30]:
                report.append(f" [{alert['timestamp']}] [{alert['severity']}] {alert['source']}: {alert['message']}")
                report.append(f"   Action: {alert['action']}")
                report.append("")
                
        report_text = "\n".join(report)
        return Response(
            report_text,
            mimetype="text/plain",
            headers={"Content-disposition": f"attachment; filename=Network_Report_{time.strftime('%Y%m%d_%H%M%S')}.txt"}
        )
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/admin/maintenance')
def admin_maintenance():
    return render_template('admin/maintenance.html')

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Return app settings that can be changed by admin."""
    return jsonify({
        'scan_mode': Config.SCAN_MODE  # 'auto' or 'manual'
    })

@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Update app settings (admin only)."""
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    data = request.json
    
    # Update scan_mode
    if 'scan_mode' in data:
        new_mode = data['scan_mode']
        if new_mode not in ('auto', 'manual'):
            return jsonify({'status': 'error', 'message': 'Invalid scan_mode value'}), 400
        Config.SCAN_MODE = new_mode
    
    # Persist to config.json
    try:
        config_path = getattr(Config, 'ACTIVE_CONFIG_PATH', None)
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                cfg = json.load(f)
            cfg['SCAN_MODE'] = Config.SCAN_MODE
            with open(config_path, 'w') as f:
                json.dump(cfg, f, indent=4)
    except Exception as e:
        print(f"[SETTINGS] Error saving config: {e}")
    
    return jsonify({'status': 'success', 'message': 'Settings updated successfully.'})

@app.route('/admin/invoice/<int:bill_id>')
def admin_view_invoice(bill_id):
    return render_template('admin/invoice_view.html', bill_id=bill_id)

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
                b.invoice_no as original_doc_id,
                b.payment_mode,
                (SELECT id FROM bills WHERE source_bill_id = rl.bill_id LIMIT 1) as new_bill_id,
                (SELECT invoice_no FROM bills WHERE source_bill_id = rl.bill_id LIMIT 1) as new_invoice_no
            FROM returns_log rl
            LEFT JOIN bills b ON rl.bill_id = b.id
            WHERE DATE(rl.return_date) >= %s AND DATE(rl.return_date) <= %s
            ORDER BY b.id ASC
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
                'doc_id': log['original_doc_id'] or f"{log['bill_id']:05d}",
                'original_doc': log['original_doc_id'] or f"{log['bill_id']:05d}",
                'new_doc': log['new_invoice_no'] or (f"{new_id:05d}" if new_id else None),
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

@app.route('/api/reports/corrections')
def get_corrections_report():
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    conn = get_db_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    
    try:
        # We look for bills that are Cancelled or RETURNED
        # and try to find any bills that were created as a replacement (source_bill_id)
        query = """
            SELECT 
                b1.id, b1.invoice_no, b1.bill_date, b1.total_amount as current_amt, 
                b1.prev_total as original_amt, b1.status, b1.payment_mode, b1.created_by,
                (SELECT GROUP_CONCAT(reason) FROM returns_log WHERE bill_id = b1.id) as reasons,
                b2.id as new_bill_id, b2.invoice_no as new_invoice, b2.total_amount as new_amt
            FROM bills b1
            LEFT JOIN bills b2 ON b1.id = b2.source_bill_id
            WHERE (b1.status IN ('Cancelled', 'RETURNED') OR b1.prev_total > 0)
              AND DATE(b1.bill_date) >= %s AND DATE(b1.bill_date) <= %s
            ORDER BY b1.id ASC
        """
        cursor.execute(query, (start_date, end_date))
        data = cursor.fetchall()
        
        results = []
        seen_ids = set()
        for row in data:
            if row['id'] in seen_ids: continue
            seen_ids.add(row['id'])
            
            orig = float(row['original_amt'] or row['current_amt'] or 0)
            curr = float(row['new_amt'] if row['new_amt'] is not None else row['current_amt'])
            diff = curr - orig
            
            results.append({
                'date': row['bill_date'].isoformat() if row['bill_date'] else None,
                'bill_no': row['invoice_no'] or f"{row['id']:05d}",
                'original_amt': orig,
                'corrected_amt': curr,
                'difference': diff,
                'reason': row['reasons'] or 'Correction',
                'status': row['status'],
                'new_bill_no': row['new_invoice'] or (f"{row['new_bill_id']:05d}" if row['new_bill_id'] else None)
            })
            
        return jsonify(results)
    except Exception as e:
        print(f"Correction Report Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

def normalize_category(product_name, product_category, product_barcode):
    cat = (product_category or '').upper()
    name = (product_name or '').upper()
    bc = (product_barcode or '')
    
    if 'OILS' in cat:
        return 'OILS'
    elif 'SPICES' in cat:
        return 'SPICES'
    elif 'TEA' in cat:
        return 'TEA/COFFEE'
    elif 'AROM' in cat:
        return 'AROMATICS'
    elif 'CAND' in cat or 'NATUR' in cat or 'CANDIES' in cat:
        return 'CANDIES'
    elif 'MRD' in cat or 'CFC' in cat or 'CHOCO' in cat or 'MRD' in name or 'CHOCO' in name or 'CFC' in name:
        if bc.startswith('18') or bc.startswith('8'):
            return 'CFC'
        else:
            return 'C-MRD'
    elif 'JELLY' in cat or 'FRUIT' in cat or 'JELLY' in name or 'FRUIT' in name:
        if bc.startswith('195') or bc.startswith('95') or 'VARKEY' in name:
            return 'VARKEY'
        else:
            return 'FRUIT JELLY'
    elif 'VARKEY' in cat or 'VARKEY' in name:
        return 'VARKEY'
    else:
        return 'OTHERS'

@app.route('/api/reports/sales-detailed')
def get_detailed_sales_report():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT 
                b.bill_date, b.id as bill_id, b.invoice_no, b.status as bill_status, b.payment_mode,
                b.total_amount as bill_total, b.tsc_percent, b.tsc_amount,
                bi.product_name, bi.qty, bi.amount, bi.rate, bi.bizz_percent, bi.bizz_amount,
                p.category, p.barcode
            FROM bill_items bi
            JOIN bills b ON bi.bill_id = b.id
            LEFT JOIN products p ON bi.product_name = p.name
            ORDER BY b.id ASC
        """
        cursor.execute(query)
        data = cursor.fetchall()
        conn.close()
        
        for row in data:
            row['qty'] = float(row['qty'] or 0)
            row['amount'] = float(row['amount'] or 0)
            row['rate'] = float(row['rate'] or 0)
            row['bizz_percent'] = float(row.get('bizz_percent') or 0)
            row['bizz_amount'] = float(row.get('bizz_amount') or 0)
            row['bill_total'] = float(row.get('bill_total') or 0)
            row['tsc_percent'] = float(row.get('tsc_percent') or 0)
            row['tsc_amount'] = float(row.get('tsc_amount') or 0)
            
            # Normalize category using unified logic
            row['category'] = normalize_category(row['product_name'], row['category'], row['barcode'])
            
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
            LPAD(b.id, 5, '0') as id,
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
        ORDER BY b.id ASC
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
        ORDER BY id ASC
    """)
    expenses = cursor.fetchall()
    
    master = sales + expenses
    master.sort(key=lambda x: (x['date'], x['id']))
    
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
                p.category,
                p.barcode,
                bi.product_name,
                bi.amount as amt
            FROM bill_items bi
            JOIN bills b ON bi.bill_id = b.id
            LEFT JOIN products p ON bi.product_name = p.name
            WHERE DATE(b.bill_date) = %s AND b.status != 'Cancelled'
        """, (d_str,))
        cats = cursor.fetchall()
        
        cat_map = {
            'OILS': 0.0,
            'SPICES': 0.0,
            'TEA/COFFEE': 0.0,
            'AROMATICS': 0.0,
            'OTHERS': 0.0,
            'CANDIES': 0.0,
            'C-MRD': 0.0,
            'CFC': 0.0,
            'FRUIT JELLY': 0.0,
            'VARKEY': 0.0
        }
        for c in cats:
            normalized = normalize_category(c['product_name'], c['category'], c['barcode'])
            if normalized in cat_map:
                cat_map[normalized] += float(c['amt'] or 0)
            else:
                cat_map['OTHERS'] += float(c['amt'] or 0)
            
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
        username = session.get('username', '').lower()
        if username in ['counter1', 'counter2']:
            user_filter = " AND b.created_by IN (%s, %s)"
            query_params.extend(['counter1', 'counter2'])
        elif username in ['counter3', 'counter4']:
            user_filter = " AND b.created_by IN (%s, %s)"
            query_params.extend(['counter3', 'counter4'])
        else:
            user_filter = " AND b.created_by = %s"
            query_params.append(session.get('username'))

    # Category-specific filtering based on Counter is disabled as all products should be included in all reports, but we keep the title/text designations
    username = session.get('username', '').lower()
    cat_filter = ""

    try:
        # 1. Sales Summary — always count ALL bills by this user (no cat_filter here)
        # cat_filter only applies to the category breakdown table, not total sales.
        cursor.execute(f"""
            SELECT 
                COUNT(*) as bill_count,
                SUM(total_amount) as total_sales,
                SUM(CASE WHEN UPPER(payment_mode) = 'CASH' THEN total_amount ELSE 0 END) as cash_sales,
                SUM(CASE WHEN UPPER(payment_mode) = 'CARD' THEN total_amount ELSE 0 END) as card_sales,
                SUM(CASE WHEN UPPER(payment_mode) = 'UPI' THEN total_amount ELSE 0 END) as upi_sales
            FROM bills b
            WHERE DATE(b.bill_date) = %s AND b.status != 'Cancelled'{user_filter}
        """, tuple(query_params))
            
        sales = cursor.fetchone() or {}
        for k in list(sales.keys()): sales[k] = float(sales[k] or 0)
        if 'bill_count' not in sales: sales = {'bill_count': 0, 'total_sales': 0.0, 'cash_sales': 0.0, 'card_sales': 0.0, 'upi_sales': 0.0}
        sales['credit_sales'] = 0.0
        sales['avg_bill'] = sales['total_sales'] / sales['bill_count'] if sales['bill_count'] > 0 else 0

        # 2. Bizz Charges (Filtered by Category if Counter)
        cursor.execute(f"""
            SELECT SUM(bi.bizz_amount) as total_bizz
            FROM bill_items bi
            JOIN bills b ON bi.bill_id = b.id
            LEFT JOIN products p ON bi.product_name = p.name
            WHERE DATE(b.bill_date) = %s AND b.status != 'Cancelled'{user_filter}{cat_filter}
        """, tuple(query_params))
        total_biz = round(float(cursor.fetchone()['total_bizz'] or 0))
        biz_80 = round(total_biz * 0.8)
        biz_20 = total_biz - biz_80

        # 3. TSC (80/20 split) - TSC is generally on the total bill, but for departmental reports, 
        # we calculate it proportionally to the departmental sales if a filter is active.
        if cat_filter:
            cursor.execute(f"""
                SELECT SUM(bi.amount * (b.tsc_percent / 100)) as total_tsc
                FROM bill_items bi
                JOIN bills b ON bi.bill_id = b.id
                LEFT JOIN products p ON bi.product_name = p.name
                WHERE DATE(b.bill_date) = %s AND b.status != 'Cancelled'{user_filter}{cat_filter}
            """, tuple(query_params))
        else:
            cursor.execute(f"""
                SELECT SUM(tsc_amount) as total_tsc
                FROM bills b
                WHERE DATE(b.bill_date) = %s AND b.status != 'Cancelled'{user_filter.replace('b.', '')}
            """, tuple(query_params))
        
        total_tsc = round(float(cursor.fetchone()['total_tsc'] or 0))
        tsc_80 = round(total_tsc * 0.8)
        tsc_20 = total_tsc - tsc_80

        # 4. Categories (Filtered)
        cursor.execute(f"""
            SELECT p.category, SUM(bi.amount) as category_sales
            FROM bill_items bi
            JOIN bills b ON bi.bill_id = b.id
            LEFT JOIN products p ON bi.product_name = p.name
            WHERE DATE(b.bill_date) = %s AND b.status != 'Cancelled'{user_filter}{cat_filter}
            GROUP BY p.category
        """, tuple(query_params))
        categories = cursor.fetchall()

        for c in categories:
            if not c['category']: c['category'] = 'General'
            c['category_sales'] = float(c['category_sales'] or 0)
            c['percent'] = (c['category_sales'] / sales['total_sales'] * 100) if sales['total_sales'] > 0 else 0

        # Ensure relevant categories appear
        cat_names = [c['category'].upper() for c in categories]
        if username in ['counter1', 'counter2'] and 'OILS' not in cat_names:
            categories.append({'category': 'OILS', 'category_sales': 0.0, 'percent': 0.0})
        elif username in ['counter3', 'counter4'] and not any('CHOCO' in name for name in cat_names):
            categories.append({'category': 'CHOCOLATES', 'category_sales': 0.0, 'percent': 0.0})
        elif username not in ['counter1', 'counter2', 'counter3', 'counter4']:
            if 'OILS' not in cat_names:
                categories.append({'category': 'OILS', 'category_sales': 0.0, 'percent': 0.0})
            if not any('CHOCO' in name for name in cat_names):
                categories.append({'category': 'CHOCOLATES', 'category_sales': 0.0, 'percent': 0.0})

        # 5. Expenses
        cursor.execute("SELECT * FROM expenses WHERE DATE(expense_date) = %s", (report_date,))
        expenses_raw = cursor.fetchall()
        office_exps = []
        shop_exps = []
        total_exc = 0.0
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
            balance = {'opening_balance': 2500, 'actual_closing': 0, 'difference': 0}
        else:
            balance['opening_balance'] = float(balance['opening_balance'])
            balance['actual_closing'] = float(balance['actual_closing'])

        denoms = []
        if 'id' in balance:
            cursor.execute("SELECT * FROM denominations WHERE balance_id = %s", (balance['id'],))
            denoms = cursor.fetchall()

        u = session.get('username', 'SYSTEM')
        u_lower = u.lower()
        counter_type = "CONSOLIDATED REPORT"
        if u_lower in ['counter1', 'counter2']:
            counter_type = f"OIL SECTION - Counter {u_lower.replace('counter', '')}"
        elif u_lower in ['counter3', 'counter4']:
            counter_type = f"CHOCOLATE SECTION - Counter {u_lower.replace('counter', '')}"
        elif u_lower == 'counter':
            counter_type = "OIL SECTION"
        elif u_lower.startswith('counter'):
            counter_type = f"Counter {u_lower.replace('counter', '')}"

        # 7. Counter Breakdown
        cursor.execute(f"""
            SELECT created_by as counter, SUM(total_amount) as amount
            FROM bills b
            WHERE DATE(b.bill_date) = %s AND b.status != 'Cancelled'{user_filter}
            GROUP BY created_by
        """, tuple(query_params))
        counter_breakdown = cursor.fetchall()
        for c in counter_breakdown:
            c['amount'] = float(c['amount'] or 0)
            
            # Fetch Oil sales for this counter
            cursor.execute(f"""
                SELECT SUM(bi.amount) as cat_sales
                FROM bills b
                JOIN bill_items bi ON b.id = bi.bill_id
                LEFT JOIN products p ON bi.product_name = p.name
                WHERE DATE(b.bill_date) = %s AND b.status != 'Cancelled' AND b.created_by = %s AND p.category = %s
            """, (query_params[0], c['counter'], 'OILS'))
            c['oil_sales'] = float((cursor.fetchone() or {}).get('cat_sales') or 0)

            # Fetch Chocolate sales for this counter
            cursor.execute(f"""
                SELECT SUM(bi.amount) as cat_sales
                FROM bills b
                JOIN bill_items bi ON b.id = bi.bill_id
                LEFT JOIN products p ON bi.product_name = p.name
                WHERE DATE(b.bill_date) = %s AND b.status != 'Cancelled' AND b.created_by = %s AND p.category LIKE 'CHOCO%%'
            """, (query_params[0], c['counter']))
            c['choco_sales'] = float((cursor.fetchone() or {}).get('cat_sales') or 0)

        conn.close()
        return jsonify({
            'meta': {
                'username': u, 
                'counter_type': counter_type,
                'time': datetime.datetime.now().strftime('%H:%M:%S')
            },
            'sales': sales,
            'biz_charges': total_biz, 'biz_80': biz_80, 'biz_20': biz_20,
            'tsc_total': total_tsc, 'tsc_80': tsc_80, 'tsc_20': tsc_20,
            'categories': categories,
            'counter_breakdown': counter_breakdown,
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
            SUM(CASE WHEN UPPER(payment_mode) = 'UPI' THEN total_amount ELSE 0 END) as upi_sales
        FROM bills 
        WHERE DATE(bill_date) BETWEEN %s AND %s AND status != 'Cancelled'
    """, (start_date, end_date))
    sales_summary = cursor.fetchone()
    sales_summary['credit_sales'] = 0.0
    
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
            ORDER BY created_by, id ASC
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
        
        cursor.execute("SELECT SUM(tsc_amount) FROM bills WHERE DATE(bill_date) = %s AND status!='Cancelled'", (report_date,))
        total_tsc = float(cursor.fetchone()[0] or 0)
        
        expected_closing = opening_bal + (cash_sales - total_exp)
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
        
        cursor.execute("SELECT SUM(tsc_amount) FROM bills WHERE DATE(bill_date) = %s AND status!='Cancelled'", (report_date,))
        total_tsc = float(cursor.fetchone()[0] or 0)
        
        # Denominations Total
        actual_closing = 0
        for d in data.get('denominations', []):
            actual_closing += (int(d['note_value']) * int(d['count']))
            
        expected_closing = opening_bal + (cash_sales - total_exp)
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
        trigger_immediate_sync()
        return jsonify({'status': 'success'})
    except Exception as e:
        if conn: conn.rollback(); conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/stock/daily-report')
def get_daily_stock_report():
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    conn = get_db_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    
    try:
        if start_date and end_date:
            start_dt = f"{start_date} 00:00:00"
            end_dt = f"{end_date} 23:59:59"
            
            # 1. Fetch all products
            cursor.execute("SELECT id, barcode, name, category, current_stock, unit FROM products")
            products = cursor.fetchall()
            
            # Sort products in Python to be database-agnostic (handles MySQL and Postgres)
            def get_sort_key(p):
                bc = p.get('barcode') or ''
                try:
                    return (0, float(bc), bc)
                except ValueError:
                    return (1, 0.0, bc)
            products.sort(key=get_sort_key)
            
            # Map products by ID
            results = {}
            for p in products:
                results[p['id']] = {
                    'barcode': p['barcode'],
                    'name': p['name'],
                    'category': p['category'],
                    'unit': p['unit'],
                    'current_stock': float(p['current_stock'] or 0),
                    'sales_during': 0.0,
                    'sales_after': 0.0,
                    'transfers_in_during': 0.0,
                    'transfers_in_after': 0.0,
                    'transfers_out_during': 0.0,
                    'transfers_out_after': 0.0,
                    'adjustments_pos_during': 0.0,
                    'adjustments_neg_during': 0.0,
                    'adjustments_after': 0.0,
                    'returns_during': 0.0,
                    'returns_after': 0.0,
                    'voids_during': 0.0,
                    'voids_after': 0.0,
                }
            
            # 2. Sales during range
            cursor.execute("""
                SELECT p.id, COALESCE(SUM(bi.qty), 0) as qty
                FROM bill_items bi
                JOIN bills b ON bi.bill_id = b.id
                JOIN products p ON bi.product_name = p.name
                WHERE b.bill_date BETWEEN %s AND %s AND b.status != 'Cancelled'
                GROUP BY p.id
            """, (start_dt, end_dt))
            for row in cursor.fetchall():
                if row['id'] in results:
                    results[row['id']]['sales_during'] = float(row['qty'])
                    
            # 3. Sales after range
            cursor.execute("""
                SELECT p.id, COALESCE(SUM(bi.qty), 0) as qty
                FROM bill_items bi
                JOIN bills b ON bi.bill_id = b.id
                JOIN products p ON bi.product_name = p.name
                WHERE b.bill_date > %s AND b.status != 'Cancelled'
                GROUP BY p.id
            """, (end_dt,))
            for row in cursor.fetchall():
                if row['id'] in results:
                    results[row['id']]['sales_after'] = float(row['qty'])
                    
            # 4. Transfers during range
            cursor.execute("""
                SELECT p.id, st.transfer_type, COALESCE(SUM(st.qty), 0) as qty
                FROM stock_transfers st
                JOIN products p ON st.product_barcode = p.barcode
                WHERE st.transfer_date BETWEEN %s AND %s
                GROUP BY p.id, st.transfer_type
            """, (start_dt, end_dt))
            for row in cursor.fetchall():
                pid = row['id']
                if pid in results:
                    ttype = row['transfer_type'].upper()
                    if ttype == 'IN':
                        results[pid]['transfers_in_during'] = float(row['qty'])
                    elif ttype == 'OUT':
                        results[pid]['transfers_out_during'] = float(row['qty'])
                        
            # 5. Transfers after range
            cursor.execute("""
                SELECT p.id, st.transfer_type, COALESCE(SUM(st.qty), 0) as qty
                FROM stock_transfers st
                JOIN products p ON st.product_barcode = p.barcode
                WHERE st.transfer_date > %s
                GROUP BY p.id, st.transfer_type
            """, (end_dt,))
            for row in cursor.fetchall():
                pid = row['id']
                if pid in results:
                    ttype = row['transfer_type'].upper()
                    if ttype == 'IN':
                        results[pid]['transfers_in_after'] = float(row['qty'])
                    elif ttype == 'OUT':
                        results[pid]['transfers_out_after'] = float(row['qty'])
                        
            # 6. Adjustments during range
            cursor.execute("""
                SELECT product_id,
                       COALESCE(SUM(CASE WHEN qty_change > 0 THEN qty_change ELSE 0 END), 0) as qty_pos,
                       COALESCE(SUM(CASE WHEN qty_change < 0 THEN qty_change ELSE 0 END), 0) as qty_neg
                FROM stock_movements
                WHERE created_at BETWEEN %s AND %s AND movement_type = 'ADJUSTMENT'
                GROUP BY product_id
            """, (start_dt, end_dt))
            for row in cursor.fetchall():
                pid = row['product_id']
                if pid in results:
                    results[pid]['adjustments_pos_during'] = float(row['qty_pos'])
                    results[pid]['adjustments_neg_during'] = float(row['qty_neg'])
                    
            # 7. Adjustments after range
            cursor.execute("""
                SELECT product_id, COALESCE(SUM(qty_change), 0) as qty
                FROM stock_movements
                WHERE created_at > %s AND movement_type = 'ADJUSTMENT'
                GROUP BY product_id
            """, (end_dt,))
            for row in cursor.fetchall():
                pid = row['product_id']
                if pid in results:
                    results[pid]['adjustments_after'] = float(row['qty'])
            
            # Determine return date column name
            ret_col = "return_date"
            try:
                cursor.execute("SELECT return_date FROM returns_log LIMIT 1")
                cursor.fetchall()
            except Exception:
                ret_col = "returned_at"
                
            # 8. Returns during range
            cursor.execute(f"""
                SELECT p.id, COALESCE(SUM(r.qty), 0) as qty
                FROM returns_log r
                JOIN products p ON r.product_code = p.barcode
                WHERE r.{ret_col} BETWEEN %s AND %s AND r.action = 'restock'
                GROUP BY p.id
            """, (start_dt, end_dt))
            for row in cursor.fetchall():
                if row['id'] in results:
                    results[row['id']]['returns_during'] = float(row['qty'])
                    
            # 9. Returns after range
            cursor.execute(f"""
                SELECT p.id, COALESCE(SUM(r.qty), 0) as qty
                FROM returns_log r
                JOIN products p ON r.product_code = p.barcode
                WHERE r.{ret_col} > %s AND r.action = 'restock'
                GROUP BY p.id
            """, (end_dt,))
            for row in cursor.fetchall():
                if row['id'] in results:
                    results[row['id']]['returns_after'] = float(row['qty'])
                    
            # 10. Voids during range (created before start_dt but cancelled/voided during range)
            try:
                cursor.execute("""
                    SELECT p.id, COALESCE(SUM(bi.qty), 0) as qty
                    FROM bill_items bi
                    JOIN bills b ON bi.bill_id = b.id
                    JOIN products p ON bi.product_name = p.name
                    JOIN audit_logs al ON al.table_name = 'bills' AND al.record_id = b.id
                    WHERE b.bill_date < %s AND al.action_time BETWEEN %s AND %s AND al.action IN ('CANCEL_BILL_PROCESS', 'VOID_BILL', 'DELETE_BILL')
                    GROUP BY p.id
                """, (start_dt, start_dt, end_dt))
                for row in cursor.fetchall():
                    if row['id'] in results:
                        results[row['id']]['voids_during'] = float(row['qty'])
            except Exception as e:
                print(f"[Daily Stock Report Voids During Error] {e}")
                
            # 11. Voids after range (created before end_dt but cancelled/voided after end_dt)
            try:
                cursor.execute("""
                    SELECT p.id, COALESCE(SUM(bi.qty), 0) as qty
                    FROM bill_items bi
                    JOIN bills b ON bi.bill_id = b.id
                    JOIN products p ON bi.product_name = p.name
                    JOIN audit_logs al ON al.table_name = 'bills' AND al.record_id = b.id
                    WHERE b.bill_date <= %s AND al.action_time > %s AND al.action IN ('CANCEL_BILL_PROCESS', 'VOID_BILL', 'DELETE_BILL')
                    GROUP BY p.id
                """, (end_dt, end_dt))
                for row in cursor.fetchall():
                    if row['id'] in results:
                        results[row['id']]['voids_after'] = float(row['qty'])
            except Exception as e:
                print(f"[Daily Stock Report Voids After Error] {e}")

            # Assemble report data
            report_data = []
            for pid, r in results.items():
                closing_stock = (
                    r['current_stock']
                    + r['sales_after']
                    - r['returns_after']
                    - r['voids_after']
                    - r['transfers_in_after']
                    + r['transfers_out_after']
                    - r['adjustments_after']
                )
                
                opening_stock = (
                    closing_stock
                    + r['sales_during']
                    - r['returns_during']
                    - r['voids_during']
                    - r['transfers_in_during']
                    + r['transfers_out_during']
                    - r['adjustments_pos_during']
                    - r['adjustments_neg_during']
                )
                
                stock_received = r['adjustments_pos_during'] + r['adjustments_neg_during'] + r['returns_during'] + r['voids_during']
                transfer = r['transfers_in_during'] - r['transfers_out_during']
                sales = r['sales_during']
                
                report_data.append({
                    'barcode': r['barcode'],
                    'name': r['name'],
                    'category': r['category'],
                    'unit': r['unit'],
                    'opening_stock': opening_stock,
                    'stock_received': stock_received,
                    'transfer': transfer,
                    'sales': sales,
                    'closing_stock': closing_stock,
                    'stock': closing_stock
                })
            conn.close()
            return jsonify(report_data)
        else:
            # Fallback to simple current stock report
            cursor.execute("SELECT barcode, name, category, current_stock as stock, unit FROM products")
            data = cursor.fetchall()
            
            # Sort products in Python to be database-agnostic (handles MySQL and Postgres)
            def get_sort_key(p):
                bc = p.get('barcode') or ''
                try:
                    return (0, float(bc), bc)
                except ValueError:
                    return (1, 0.0, bc)
            data.sort(key=get_sort_key)
            conn.close()
            for row in data:
                row['stock'] = float(row['stock'] or 0)
                row['opening_stock'] = row['stock']
                row['stock_received'] = 0.0
                row['transfer'] = 0.0
                row['sales'] = 0.0
                row['closing_stock'] = row['stock']
            return jsonify(data)
    except Exception as e:
        if conn: conn.close()
        print(f"[Daily Stock Report Endpoint Error] {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/reports/final-stock')
def get_final_stock_report_api():
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    conn = get_db_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    
    try:
        if start_date and end_date:
            start_dt = f"{start_date} 00:00:00"
            end_dt = f"{end_date} 23:59:59"
            
            # 1. Fetch all products
            cursor.execute("SELECT id, barcode, name, category, current_stock, unit FROM products")
            products = cursor.fetchall()
            
            # Sort products database-agnostically
            def get_sort_key(p):
                bc = p.get('barcode') or ''
                try:
                    return (0, float(bc), bc)
                except ValueError:
                    return (1, 0.0, bc)
            products.sort(key=get_sort_key)
            
            # Map products by ID
            results = {}
            for p in products:
                results[p['id']] = {
                    'barcode': p['barcode'],
                    'name': p['name'],
                    'category': p['category'],
                    'unit': p['unit'],
                    'current_stock': float(p['current_stock'] or 0),
                    'sales_after': 0.0,
                    'transfers_in_after': 0.0,
                    'transfers_out_after': 0.0,
                    'adjustments_after': 0.0,
                    'returns_after': 0.0,
                    'voids_after': 0.0,
                }
            
            # 2. Sales after range
            cursor.execute("""
                SELECT p.id, COALESCE(SUM(bi.qty), 0) as qty
                FROM bill_items bi
                JOIN bills b ON bi.bill_id = b.id
                JOIN products p ON bi.product_name = p.name
                WHERE b.bill_date > %s AND b.status != 'Cancelled'
                GROUP BY p.id
            """, (end_dt,))
            for row in cursor.fetchall():
                if row['id'] in results:
                    results[row['id']]['sales_after'] = float(row['qty'])
                    
            # 3. Transfers after range
            try:
                cursor.execute("""
                    SELECT p.id, st.transfer_type, COALESCE(SUM(st.qty), 0) as qty
                    FROM stock_transfers st
                    JOIN products p ON st.product_barcode = p.barcode
                    WHERE st.transfer_date > %s
                    GROUP BY p.id, st.transfer_type
                """, (end_dt,))
                for row in cursor.fetchall():
                    pid = row['id']
                    if pid in results:
                        ttype = row['transfer_type'].upper()
                        if ttype == 'IN':
                            results[pid]['transfers_in_after'] = float(row['qty'])
                        elif ttype == 'OUT':
                            results[pid]['transfers_out_after'] = float(row['qty'])
            except Exception as e:
                print(f"[Final Stock Report Transfers After Error] {e}")
                
            # 4. Adjustments after range
            cursor.execute("""
                SELECT product_id, COALESCE(SUM(qty_change), 0) as qty
                FROM stock_movements
                WHERE created_at > %s AND movement_type = 'ADJUSTMENT'
                GROUP BY product_id
            """, (end_dt,))
            for row in cursor.fetchall():
                pid = row['product_id']
                if pid in results:
                    results[pid]['adjustments_after'] = float(row['qty'])
            
            # Determine return date column name
            ret_col = "return_date"
            try:
                cursor.execute("SELECT return_date FROM returns_log LIMIT 1")
                cursor.fetchall()
            except Exception:
                ret_col = "returned_at"
                
            # 5. Returns after range
            cursor.execute(f"""
                SELECT p.id, COALESCE(SUM(r.qty), 0) as qty
                FROM returns_log r
                JOIN products p ON r.product_code = p.barcode
                WHERE r.{ret_col} > %s AND r.action = 'restock'
                GROUP BY p.id
            """, (end_dt,))
            for row in cursor.fetchall():
                if row['id'] in results:
                    results[row['id']]['returns_after'] = float(row['qty'])
                    
            # 6. Voids after range
            try:
                cursor.execute("""
                    SELECT p.id, COALESCE(SUM(bi.qty), 0) as qty
                    FROM bill_items bi
                    JOIN bills b ON bi.bill_id = b.id
                    JOIN products p ON bi.product_name = p.name
                    JOIN audit_logs al ON al.table_name = 'bills' AND al.record_id = b.id
                    WHERE b.bill_date <= %s AND al.action_time > %s AND al.action IN ('CANCEL_BILL_PROCESS', 'VOID_BILL', 'DELETE_BILL')
                    GROUP BY p.id
                """, (end_dt, end_dt))
                for row in cursor.fetchall():
                    if row['id'] in results:
                        results[row['id']]['voids_after'] = float(row['qty'])
            except Exception as e:
                print(f"[Final Stock Report Voids After Error] {e}")
                
            # Assemble report data
            report_data = []
            for pid, r in results.items():
                closing_stock = (
                    r['current_stock']
                    + r['sales_after']
                    - r['returns_after']
                    - r['voids_after']
                    - r['transfers_in_after']
                    + r['transfers_out_after']
                    - r['adjustments_after']
                )
                
                report_data.append({
                    'barcode': r['barcode'],
                    'name': r['name'],
                    'category': r['category'],
                    'unit': r['unit'],
                    'qty': closing_stock,
                    'godown': ''
                })
            conn.close()
            return jsonify(report_data)
        else:
            # Fallback to simple current stock report
            cursor.execute("SELECT barcode, name, category, current_stock as qty, unit FROM products")
            data = cursor.fetchall()
            
            # Sort products database-agnostically
            def get_sort_key(p):
                bc = p.get('barcode') or ''
                try:
                    return (0, float(bc), bc)
                except ValueError:
                    return (1, 0.0, bc)
            data.sort(key=get_sort_key)
            conn.close()
            for row in data:
                row['qty'] = float(row['qty'] or 0)
                row['godown'] = ''
            return jsonify(data)
    except Exception as e:
        if conn: conn.close()
        print(f"[Final Stock Report Endpoint Error] {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/reports/daily-position')
def get_daily_position_report():
    conn = get_db_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    
    report_date = request.args.get('date')
    if not report_date:
        report_date = datetime.date.today().isoformat()
        
    is_pg = getattr(conn, 'is_pg', False) or getattr(conn, 'connection_id', '') == 'postgres'
    
    if is_pg:
        # PostgreSQL query - using cast for DATE and conditional regex check for numeric barcode sort
        query = """
            SELECT 
                p.barcode as code, 
                p.name as product_name, 
                p.current_stock as closing,
                COALESCE(SUM(CASE WHEN CAST(b.bill_date AS DATE) = %s AND b.status != 'Cancelled' THEN bi.qty ELSE 0 END), 0) as outgoing,
                p.category,
                p.unit as unit
            FROM daily_position_list dp
            JOIN products p ON dp.barcode = p.barcode
            LEFT JOIN bill_items bi ON p.name = bi.product_name
            LEFT JOIN bills b ON bi.bill_id = b.id
            GROUP BY p.barcode, p.name, p.current_stock, p.category, p.unit
            ORDER BY CASE WHEN p.barcode ~ '^[0-9]+$' THEN CAST(p.barcode AS BIGINT) ELSE 0 END, p.barcode
        """
    else:
        # MySQL query - standard CURDATE replaced with input date
        query = """
            SELECT 
                p.barcode as code, 
                p.name as product_name, 
                p.current_stock as closing,
                COALESCE(SUM(CASE WHEN DATE(b.bill_date) = %s AND b.status != 'Cancelled' THEN bi.qty ELSE 0 END), 0) as outgoing,
                p.category,
                p.unit as unit
            FROM daily_position_list dp
            JOIN products p ON dp.barcode = p.barcode
            LEFT JOIN bill_items bi ON p.name = bi.product_name
            LEFT JOIN bills b ON bi.bill_id = b.id
            GROUP BY p.barcode, p.name, p.current_stock, p.category, p.unit
            ORDER BY (p.barcode + 0), p.barcode
        """
        
    cursor.execute(query, (report_date,))
    data = cursor.fetchall()
    conn.close()
    
    for row in data:
        row['closing'] = float(row['closing'] or 0)
        row['outgoing'] = float(row['outgoing'] or 0)
        row['unit'] = row.get('unit') or 'PCS'
        if row['outgoing'] == 0: row['outgoing'] = ""
        
    return jsonify(data)

@app.route('/api/reports/daily-position/add', methods=['POST'])
def add_to_daily_position():
    data = request.json
    barcode = data.get('barcode')
    if not barcode: return jsonify({'status': 'error', 'message': 'No barcode'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT IGNORE INTO daily_position_list (barcode) VALUES (%s)", (barcode,))
        conn.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/reports/daily-position/remove', methods=['POST'])
def remove_from_daily_position():
    data = request.json
    barcode = data.get('barcode')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM daily_position_list WHERE barcode = %s", (barcode,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/stock/transfers')
def get_stock_transfers():
    conn = get_db_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    
    start = request.args.get('start')
    end = request.args.get('end')
    
    try:
        # Ensure transfer_type column exists (safe idempotent check)
        try:
            cursor.execute("ALTER TABLE stock_transfers ADD COLUMN transfer_type VARCHAR(10) DEFAULT 'OUT'")
            conn.commit()
        except:
            conn.rollback()
            
        if start and end:
            cursor.execute("""
                SELECT transfer_date, product_barcode, product_name, qty,
                       from_location, to_location, transfer_type, pushed_by
                FROM stock_transfers
                WHERE DATE(transfer_date) >= %s AND DATE(transfer_date) <= %s
                ORDER BY transfer_date DESC
            """, (start, end))
        else:
            cursor.execute("""
                SELECT transfer_date, product_barcode, product_name, qty,
                       from_location, to_location, transfer_type, pushed_by
                FROM stock_transfers ORDER BY transfer_date DESC
            """)
        data = cursor.fetchall()
    except Exception as e:
        print(f"[Transfer Report Error] {e}")
        data = []
    conn.close()
    for row in data:
        row['qty'] = float(row['qty'] or 0)
        row['transfer_type'] = row.get('transfer_type') or 'OUT'
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

@app.route('/sales/preview')
def sales_preview():
    return render_template('sales/preview_bills.html')

@app.route('/sales/report')
def sales_report():
    return render_template('sales/final_report.html')

@app.route('/sales/returns')
def sales_returns():
    return render_template('sales/returns.html')


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
        socketio.emit('stock_updated', {'type': 'billing_return', 'bill_id': bill_id})
        
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
    # Query local database first for scanning speed (in milliseconds)
    conn = get_local_db_connection()
    if not conn:
        conn = get_db_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM products WHERE (name LIKE %s OR barcode = %s) LIMIT 20", (f'%{q}%', q))
    products = cursor.fetchall()
    conn.close()
    for p in products:
        p['price'] = float(p['price'])
        if p.get('bizz'): p['bizz'] = float(p['bizz'])
    return jsonify(products)

@app.route('/api/save-bill', methods=['POST'])
def save_bill():
    data = request.json
    username = session.get('username', 'SYSTEM')
    max_attempts = 3
    last_error = None

    for attempt in range(1, max_attempts + 1):
        conn = None
        try:
            conn = get_db_connection()
            if not conn:
                raise RuntimeError('Database connection failed.')

            result = create_bill(conn, data, username, log_audit)
            bill_id = result['bill_id']
            invoice_no = result['invoice_no']
            bill_dt = datetime.datetime.now()

            # Keep all slow/non-critical work outside the database transaction.
            schedule_brain_evolution(bill_id)
            trigger_immediate_sync()
            announcer.announce("update")
            socketio.emit('stock_updated', {'type': 'billing_creation', 'invoice_no': invoice_no})

            return jsonify({
                'status': 'success',
                'bill_id': bill_id,
                'invoice_no': invoice_no,
                'invoice_display': invoice_no,
                'bill_date': bill_dt.strftime('%d-%m-%Y'),
                'bill_time': bill_dt.strftime('%I:%M %p'),
                'duplicate_request': result.get('duplicate_request', False),
                'attempts': attempt,
            })
        except Exception as e:
            last_error = e
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            if attempt < max_attempts and is_retryable_db_error(e):
                time.sleep(0.12 * attempt)
                continue
            status_code = 409 if is_retryable_db_error(e) else 500
            return jsonify({'status': 'error', 'message': str(e), 'attempts': attempt}), status_code
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    return jsonify({'status': 'error', 'message': str(last_error or 'Bill save failed.'), 'attempts': max_attempts}), 500

@app.route('/api/print-thermal', methods=['POST'])
def api_print_thermal():
    data = request.json
    try:
        # Spool printing asynchronously in a background thread to prevent UI delays
        def bg_print():
            print_thermal_bill(
                items=data['items'],
                bill_no=data['bill_no'],
                bill_date=data['bill_date'],
                bill_time=data['bill_time'],
                bill_type=data['bill_type']
            )
        threading.Thread(target=bg_print, daemon=True).start()
        return jsonify({'status': 'success', 'message': 'Thermal print job spooled.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/print-closure', methods=['POST'])
def api_print_closure():
    data = request.json
    try:
        # Spool closure printing asynchronously in a background thread
        threading.Thread(target=print_closure_report, args=(data,), daemon=True).start()
        return jsonify({'status': 'success', 'message': 'Closure print job spooled.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    conn = get_db_connection()
    if not conn: return jsonify({'error': 'DB Connection failed'}), 500
    
    cursor = conn.cursor()
    today = datetime.date.today()
    
    # User-specific filtering for stats
    user_filter = ""
    query_params = [today]
    if session.get('role') == 'sales':
        username = session.get('username', '').lower()
        if username in ['counter1', 'counter2']:
            user_filter = " AND created_by IN (%s, %s)"
            query_params.extend(['counter1', 'counter2'])
        elif username in ['counter3', 'counter4']:
            user_filter = " AND created_by IN (%s, %s)"
            query_params.extend(['counter3', 'counter4'])
        else:
            user_filter = " AND created_by = %s"
            query_params.append(session.get('username'))
    
    cursor.execute(f"SELECT SUM(total_amount) FROM bills WHERE DATE(bill_date) = %s AND status != 'Cancelled'{user_filter}", tuple(query_params))
    daily_sales = cursor.fetchone()[0] or 0
    
    cursor.execute(f"SELECT COUNT(*) FROM bills WHERE DATE(bill_date) = %s AND status != 'Cancelled'{user_filter}", tuple(query_params))
    bill_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE DATE(expense_date) = %s", (today,))
    expenses = cursor.fetchone()[0] or 0
    
    # Fetch Bizz Charges (loyalty rewards paid in cash)
    cursor.execute(f"""
        SELECT SUM(bi.bizz_amount)
        FROM bill_items bi
        JOIN bills b ON bi.bill_id = b.id
        WHERE DATE(b.bill_date) = %s AND b.status != 'Cancelled'{user_filter}
    """, tuple(query_params))
    biz_charges = float(cursor.fetchone()[0] or 0)
    
    cursor.execute(f"SELECT SUM(tsc_amount) FROM bills WHERE DATE(bill_date) = %s AND status != 'Cancelled'{user_filter}", tuple(query_params))
    tsc_total = float(cursor.fetchone()[0] or 0)
    
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

    db_size_kb = fetch_database_size_kb(cursor)
    conn.close()
    avg_bill = (float(daily_sales) / bill_count) if bill_count > 0 else 0
    
    return jsonify({
        'daily_sales': float(daily_sales),
        'bill_count': bill_count,
        'expenses': float(expenses),
        'cash_sales': cash_sales,
        'upi_sales': upi_sales,
        'card_sales': card_sales,
        'biz_charges': biz_charges,
        'tsc_total': tsc_total,
        'canceled_bills': canceled_count,
        'canceled_amount': float(canceled_amount),
        'avg_bill_value': float(avg_bill),
        'db_size_kb': db_size_kb
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
        cursor.execute("SELECT SUM(total_amount) as total_amount FROM bills WHERE DATE(bill_date) = %s AND status != 'Cancelled'", (d_str,))
        amt = cursor.fetchone()['total_amount'] or 0
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

@app.route('/api/stats/abc')
def get_stats_abc():
    conn = get_db_connection()
    if not conn: return jsonify({'error': 'DB Connection failed'}), 500
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT barcode, name, category, current_stock as stock 
        FROM products 
        ORDER BY current_stock ASC
    """)
    products = cursor.fetchall()
    conn.close()
    return jsonify(products)

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
        SELECT EXTRACT(HOUR FROM bill_date) as hour, SUM(total_amount) as revenue
        FROM bills
        WHERE status != 'Cancelled'
        GROUP BY EXTRACT(HOUR FROM bill_date)
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
        username = session.get('username', '').lower()
        if username in ['counter1', 'counter2']:
            user_filter = " AND created_by IN (%s, %s)"
            query_params_today.extend(['counter1', 'counter2'])
        elif username in ['counter3', 'counter4']:
            user_filter = " AND created_by IN (%s, %s)"
            query_params_today.extend(['counter3', 'counter4'])
        else:
            user_filter = " AND created_by = %s"
            query_params_today.append(session.get('username'))

    cursor.execute(f"""
        SELECT EXTRACT(HOUR FROM bill_date) as hour, SUM(total_amount) as revenue
        FROM bills
        WHERE DATE(bill_date) = %s AND status != 'Cancelled'{user_filter}
        GROUP BY EXTRACT(HOUR FROM bill_date)
        ORDER BY hour
    """, tuple(query_params_today))
    hourly_raw = cursor.fetchall()
    
    hourly_map = {int(row['hour']): float(row['revenue']) for row in hourly_raw}
    hourly_data = []
    labels = []
    for h in range(24):
        if h == 0:
            display_str = "12AM"
        elif h == 12:
            display_str = "12PM"
        elif h < 12:
            display_str = f"{h}AM"
        else:
            display_str = f"{h-12}PM"
        labels.append(display_str)
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
    if not conn: return jsonify({'next_id': "SS-0", 'display_id': 'SS-0'})
    cursor = conn.cursor()
    cursor.execute("SELECT `last_value` FROM bill_sequences WHERE seq_date = %s", (global_key.strftime('%Y-%m-%d'),))
    res = cursor.fetchone()
    next_val = 1
    if res:
        next_val = res[0] + 1
    else:
        # Fallback to count
        cursor.execute("SELECT COUNT(*) FROM bills")
        next_val = cursor.fetchone()[0] + 1
        
    conn.close()
    return jsonify({
        'next_id': f"{next_val}",
        'display_id': f"SS-{next_val}",
    })

@app.route('/api/bills/recent')
def get_recent_bills():
    conn = get_db_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    
    bill_no = request.args.get('bill_no')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    conditions = []
    params = []
    
    if session.get('role') == 'sales':
        username = session.get('username', '').lower()
        if username in ['counter1', 'counter2']:
            conditions.append("created_by IN (%s, %s)")
            params.extend(['counter1', 'counter2'])
        elif username in ['counter3', 'counter4']:
            conditions.append("created_by IN (%s, %s)")
            params.extend(['counter3', 'counter4'])
        else:
            conditions.append("created_by = %s")
            params.append(session.get('username'))
        
    if bill_no:
        # Search by Invoice No or ID
        clean_bill_no = bill_no.strip()
        import re
        digit_match = re.search(r'\d+$', clean_bill_no)
        if digit_match:
            num_str = digit_match.group(0)
            num_val = int(num_str)
            conditions.append("""(
                LOWER(invoice_no) LIKE LOWER(%s)
                OR id = %s
                OR invoice_no LIKE %s
                OR invoice_no LIKE %s
            )""")
            params.append(f"%{clean_bill_no}%")
            params.append(num_val)
            params.append(f"%{num_val:05d}")
            params.append(f"%{num_val}")
        else:
            conditions.append("LOWER(invoice_no) LIKE LOWER(%s)")
            params.append(f"%{clean_bill_no}%")
            
    if start_date:
        conditions.append("DATE(bill_date) >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("DATE(bill_date) <= %s")
        params.append(end_date)
        
    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    
    query = f"SELECT id, invoice_no, total_amount, bill_date, status, payment_mode FROM bills{where_clause} ORDER BY id ASC LIMIT 50"
    cursor.execute(query, tuple(params))
    bills = cursor.fetchall()
    conn.close()
    for b in bills:
        b['total_amount'] = float(b['total_amount'])
        if isinstance(b['bill_date'], (datetime.datetime, datetime.date)):
            b['bill_date'] = b['bill_date'].isoformat()
    return jsonify(bills)

@app.route('/api/bills/update-payment-mode', methods=['POST'])
def update_payment_mode():
    data = request.json
    bill_id = data.get('bill_id')
    new_mode = data.get('payment_mode')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get old value for audit
        cursor.execute("SELECT payment_mode, invoice_no FROM bills WHERE id = %s", (bill_id,))
        bill = cursor.fetchone()
        if not bill:
            if conn: conn.close()
            return jsonify({'status': 'error', 'message': 'Bill not found'}), 404
        
        old_mode = bill[0]
        invoice_no = bill[1]
        
        # Update
        cursor.execute("UPDATE bills SET payment_mode = %s WHERE id = %s", (new_mode, bill_id))
        
        # Audit log
        log_audit(cursor, 'UPDATE_PAYMENT_MODE', 'bills', bill_id, old_mode, new_mode)
        
        conn.commit()
        conn.close()
        
        # Real-time trigger
        announcer.announce("update")
        
        return jsonify({'status': 'success', 'message': f'Payment mode for {invoice_no} updated to {new_mode}'})
    except Exception as e:
        if 'conn' in locals() and conn: conn.rollback(); conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/bills/all')
def get_all_bills_api():
    conn = get_db_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor(dictionary=True)
    # Fetching all columns needed by the Bill-wise report
    cursor.execute("SELECT id, invoice_no, total_amount, bill_date, status, discount, prev_total, source_bill_id, payment_mode, tsc_percent, tsc_amount FROM bills ORDER BY CAST(SUBSTRING(invoice_no, 4) AS UNSIGNED) ASC")
    bills = cursor.fetchall()
    conn.close()
    for b in bills:
        b['total_amount'] = float(b['total_amount'] or 0)
        b['discount'] = float(b.get('discount') or 0)
        b['prev_total'] = float(b.get('prev_total') or 0)
        b['tsc_amount'] = float(b.get('tsc_amount') or 0)
        b['tsc_percent'] = float(b.get('tsc_percent') or 0)
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
        if not bill: raise Exception("Bill not found")
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
    reprocess = data.get('reprocess', False)
    
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'DB fail'}), 500
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT status, total_amount FROM bills WHERE id = %s", (bill_id,))
        bill = cursor.fetchone()
        if not bill: raise Exception("Bill not found")
        if bill['status'] == 'Cancelled': 
            if not reprocess:
                return jsonify({'status': 'info', 'message': 'Already cancelled'})
            # If reprocess is true but already cancelled, we still want to load items

        # 1. Fetch items for potential re-billing OR restocking
        cursor.execute("SELECT * FROM bill_items WHERE bill_id = %s", (bill_id,))
        items = cursor.fetchall()

        # 2. Restock items (only if NOT already cancelled)
        if bill['status'] != 'Cancelled':
            for item in items:
                cursor.execute("UPDATE products SET current_stock = current_stock + %s WHERE name = %s", (item['qty'], item['product_name']))

            # 3. Mark bill as cancelled
            cursor.execute("UPDATE bills SET status = 'Cancelled', prev_total = %s, total_amount = 0 WHERE id = %s", (bill['total_amount'], bill_id))
            log_audit(cursor, 'CANCEL_BILL_PROCESS', 'bills', bill_id, f"Total: {bill['total_amount']}", "Cancelled for Correction" if reprocess else "Cancelled")

        # 4. Handle Reprocess (Loading items back to cart)
        if reprocess:
            rebill_cart = []
            for item in items:
                rebill_cart.append({
                    'name': item['product_name'],
                    'qty': float(item['qty']),
                    'rate': float(item['rate']),
                    'amount': float(item['amount']),
                    'bizz': float(item.get('bizz_percent', 0)),
                    'category': 'General'
                })
            
            session['reprocess_cart'] = rebill_cart
            session['source_bill_id'] = bill_id
            session.modified = True
            
        conn.commit(); conn.close()
        trigger_immediate_sync()
        
        # Real-time trigger
        announcer.announce("update")
        socketio.emit('stock_updated', {'type': 'billing_cancellation', 'bill_id': bill_id})
        
        return jsonify({
            'status': 'success', 
            'redirect': '/sales/billing' if reprocess else None
        })
    except Exception as e:
        if conn: conn.rollback(); conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/delete-bill', methods=['POST'])
def delete_bill():
    if session.get('role') != 'admin':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        
    data = request.json
    bill_id = data.get('bill_id')
    restore_stock = data.get('restore_stock', True)
    
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'DB fail'}), 500
    try:
        cursor = conn.cursor(dictionary=True)
        # 1. Fetch items of the bill
        cursor.execute("SELECT * FROM bill_items WHERE bill_id = %s", (bill_id,))
        items = cursor.fetchall()
        
        # 2. Get the bill status
        cursor.execute("SELECT status FROM bills WHERE id = %s", (bill_id,))
        bill = cursor.fetchone()
        if not bill: raise Exception("Bill not found")
        
        # 3. Restock items (if it wasn't already Cancelled, and if restore_stock is True)
        if restore_stock and bill['status'] != 'Cancelled':
            for item in items:
                cursor.execute("UPDATE products SET current_stock = current_stock + %s WHERE name = %s", (item['qty'], item['product_name']))
        
        # 4. Delete associated records
        cursor.execute("DELETE FROM returns_log WHERE bill_id = %s", (bill_id,))
        cursor.execute("DELETE FROM bill_items WHERE bill_id = %s", (bill_id,))
        cursor.execute("DELETE FROM stock_movements WHERE bill_id = %s", (bill_id,))
        cursor.execute("DELETE FROM bills WHERE id = %s", (bill_id,))
        
        conn.commit(); conn.close()
        trigger_immediate_sync()
        
        # Announce sync
        announcer.announce("update")
        socketio.emit('stock_updated', {'type': 'billing_deletion', 'bill_id': bill_id})
        
        return jsonify({'status': 'success', 'message': 'Bill permanently deleted from database.'})
    except Exception as e:
        if conn: conn.rollback(); conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/reports/categories')
def get_report_categories():
    conn = get_db_connection()
    if not conn: return jsonify([])
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category != '' ORDER BY category")
    cats = [row[0] for row in cursor.fetchall()]
    conn.close()
    return jsonify(cats)

@app.route('/api/inventory/next-barcode')
def get_next_barcode():
    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'DB connection failed'}), 500
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT MAX(CAST(barcode AS UNSIGNED)) as max_bc FROM products WHERE barcode REGEXP '^[0-9]+$'")
        res = cursor.fetchone()
        next_bc = (res['max_bc'] or 0) + 1
        return jsonify({'next_barcode': f"{next_bc:03d}"})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/inventory/products', methods=['GET', 'POST'])
@app.route('/api/inventory/products/<int:prod_id>', methods=['DELETE'])
def inventory_products(prod_id=None):
    # Retrieve product catalog locally for maximum rendering speed (milliseconds)
    if request.method == 'GET':
        conn = get_local_db_connection()
        if not conn:
            conn = get_db_connection()
    else:
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
            # Ensure min_threshold and current_stock are never null in the API response.
            # If the DB has NULL (possible on older client data), the JS fallback || 25
            # would silently reset the threshold to 25 on the next product save.
            p['min_threshold'] = int(p['min_threshold'] or 25)
            p['current_stock'] = float(p['current_stock'] or 0)
            if p.get('expiry_date'): p['expiry_date'] = p['expiry_date'].isoformat()
        return jsonify(res)
        
    elif request.method == 'POST':
        data = request.json
        pid = data.get('id')
        try:
            if pid:
                # NOTE: current_stock is intentionally excluded from the edit UPDATE.
                # Stock levels are managed exclusively by the billing route (consume_locked_stock)
                # and the /api/inventory/stock-adjust route. Updating current_stock here would
                # overwrite live stock with a stale form snapshot and corrupt inventory records.
                cursor.execute("""
                    UPDATE products SET barcode=%s, name=%s, category=%s, price=%s, bizz=%s, unit=%s, expiry_date=%s, min_threshold=%s
                    WHERE id = %s
                """, (data['barcode'], data['name'], data['category'], data['price'], data['bizz'],
                      data.get('unit', 'PCS'), data.get('expiry_date'), data.get('min_threshold') or 25, pid))
                log_audit(cursor, 'EDIT_PRODUCT', 'products', pid, None, data['name'])
            else:
                cursor.execute("""
                    INSERT INTO products (barcode, name, category, price, bizz, unit, expiry_date, min_threshold, current_stock)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (data['barcode'], data['name'], data['category'], data['price'], data['bizz'], 
                      data.get('unit', 'PCS'), data.get('expiry_date'), data.get('min_threshold', 25), data.get('current_stock', 0)))
                log_audit(cursor, 'ADD_PRODUCT', 'products', cursor.lastrowid, None, data['name'])
            
            conn.commit(); conn.close()
            socketio.emit('stock_updated', {'type': 'product_mutation'})
            return jsonify({'status': 'success'})
        except Exception as e:
            if conn: conn.rollback(); conn.close()
            return jsonify({'status': 'error', 'message': str(e)}), 500
            
    elif request.method == 'DELETE':
        pid = prod_id or request.json.get('id')
        try:
            cursor.execute("DELETE FROM products WHERE id = %s", (pid,))
            conn.commit(); conn.close()
            socketio.emit('stock_updated', {'type': 'product_mutation'})
            return jsonify({'status': 'success'})
        except Exception as e:
            if conn: conn.rollback(); conn.close()
            return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/inventory/stock-adjust', methods=['POST'])
def api_inventory_stock_adjust():
    data = request.json
    pid = data.get('id')
    mode = data.get('mode') 
    qty = float(data.get('qty', 0))
    reason = data.get('reason', 'Manual Adjustment')

    if not pid or qty <= 0:
        return jsonify({'status': 'error', 'message': 'Invalid input data'}), 400

    conn = get_db_connection()
    if not conn: 
        return jsonify({'status': 'error', 'message': 'DB Connection failed'}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT current_stock, name FROM products WHERE id = %s FOR UPDATE", (pid,))
        product = cursor.fetchone()
        if not product:
            conn.rollback()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Product not found'}), 404

        stock_before = float(product['current_stock'] or 0)
        diff = qty if mode == 'add' else -qty
        stock_after = stock_before + diff

        if stock_after < 0:
            conn.rollback()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Stock cannot fall below zero'}), 400

        # 1. Update products table
        cursor.execute("UPDATE products SET current_stock = %s WHERE id = %s", (stock_after, pid))

        # 2. Log movement in stock_movements table
        cursor.execute("""
            INSERT INTO stock_movements 
            (product_id, movement_type, qty_change, stock_before, stock_after, created_by) 
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (pid, 'ADJUSTMENT', diff, stock_before, stock_after, session.get('username', 'SYSTEM')))

        conn.commit()
        conn.close()
        socketio.emit('stock_updated', {'type': 'stock_adjust', 'product_id': pid, 'stock_after': stock_after})
        return jsonify({'status': 'success'})
    except Exception as e:
        if conn: conn.rollback(); conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/stock/next-reference')
def get_next_transfer_reference_route():
    transfer_key = datetime.date(2000, 1, 2)
    conn = get_db_connection()
    if not conn:
        return jsonify({'next_id': "1", 'display_id': 'TRF-1'})
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT `last_value` FROM bill_sequences WHERE seq_date = %s", (transfer_key,))
        res = cursor.fetchone()
        next_val = 1
        if res:
            next_val = res[0] + 1
        conn.close()
        return jsonify({
            'next_id': f"{next_val}",
            'display_id': f"TRF-{next_val}"
        })
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/sales/stock/transfer')
def sales_stock_transfer():
    return render_template('sales/stock_transfer.html')

@app.route('/sales/reports/transfer-report')
def sales_reports_transfer_report():
    return render_template('sales/transfer_report.html')

@app.route('/api/stock/transfer', methods=['POST'])
def api_stock_transfer():
    data = request.json
    items = data.get('items', [])
    
    # Enforce role-based transfer rules strictly on backend
    role = session.get('role')
    if role == 'admin':
        transfer_type = 'IN'
        from_loc = 'Godown'
        to_loc = 'Shop'
    else:
        # Default/Sales/Counter role
        transfer_type = 'OUT'
        from_loc = 'Shop'
        to_loc = 'Godown'
        
    reference = data.get('reference', 'GEN-TRF')

    conn = get_db_connection()
    if not conn: return jsonify({'status': 'error', 'message': 'DB fail'}), 500
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Ensure transfer_type column exists
        try:
            cursor.execute("ALTER TABLE stock_transfers ADD COLUMN transfer_type VARCHAR(10) DEFAULT 'OUT'")
            conn.commit()
        except:
            conn.rollback()
        
        # Auto-sequence reference logic if reference is AUTO, MANUAL, GEN-TRF, empty, or starts with TRF-
        is_auto = False
        ref_stripped = reference.strip() if reference else ""
        if not ref_stripped or ref_stripped == 'AUTO' or ref_stripped == 'MANUAL' or ref_stripped == 'GEN-TRF' or ref_stripped.startswith('TRF-'):
            is_auto = True
            
        if is_auto:
            transfer_key = datetime.date(2000, 1, 2)
            cursor.execute("SELECT `last_value` FROM bill_sequences WHERE seq_date = %s FOR UPDATE", (transfer_key.strftime('%Y-%m-%d'),))
            res = cursor.fetchone()
            if res:
                next_val = res['last_value'] + 1
                cursor.execute("UPDATE bill_sequences SET `last_value` = %s WHERE seq_date = %s", (next_val, transfer_key.strftime('%Y-%m-%d')))
            else:
                next_val = 1
                cursor.execute("INSERT INTO bill_sequences (seq_date, `last_value`) VALUES (%s, %s)", (transfer_key, next_val))
            reference = f"TRF-{next_val}"
        
        for item in items:
            pid = item['id']
            qty = float(item['qty'])
            # IN = stock increases (coming in), OUT = stock decreases (going out)
            diff = qty if transfer_type == 'IN' else -qty
            
            # 1. Update product stock
            cursor.execute("UPDATE products SET current_stock = current_stock + %s WHERE id = %s", (diff, pid))
            
            # 2. Log transfer record with type
            cursor.execute("SELECT barcode, name, current_stock FROM products WHERE id = %s", (pid,))
            p = cursor.fetchone()
            if p:
                cursor.execute("""
                     INSERT INTO stock_transfers
                       (product_barcode, product_name, qty, from_location, to_location, transfer_type, pushed_by)
                     VALUES (%s, %s, %s, %s, %s, %s, %s)
                 """, (
                    p['barcode'], p['name'], qty,
                    from_loc, to_loc,
                    transfer_type,
                    f"{session.get('username', 'Admin')} (Ref: {reference})"
                ))
                 
        conn.commit()
        conn.close()
        socketio.emit('stock_updated', {'type': 'stock_transfer'})
        return jsonify({'status': 'success', 'reference': reference})
    except Exception as e: 
        if conn: conn.rollback(); conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ===========================================================================
# BACKUP SYSTEM ROUTES
# ===========================================================================
from backend.backup import get_backup_manager

@app.route('/admin/backup')
def admin_backup():
    """Render the Backup Management admin page."""
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template('admin/backup.html')

@app.route('/api/admin/backup/status')
def api_backup_status():
    """Return backup status summary for dashboard card."""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    bm = get_backup_manager()
    return jsonify(bm.get_status_summary())

@app.route('/api/admin/backup/list')
def api_backup_list():
    """Return list of available backup files."""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    bm = get_backup_manager()
    return jsonify({'backups': bm.get_backup_list(), 'is_server': bm.is_server_machine()})

@app.route('/api/admin/backup/create', methods=['POST'])
def api_backup_create():
    """Trigger a manual backup. SERVER ONLY."""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    bm = get_backup_manager()
    if not bm.is_server_machine():
        return jsonify({'error': 'Backup creation is only allowed on the Server machine.', 'client_blocked': True}), 403
    result = bm.create_backup(backup_type='Manual')
    status_code = 200 if result.get('success') else 500
    return jsonify(result), status_code

@app.route('/api/admin/backup/restore', methods=['POST'])
def api_backup_restore():
    """Restore a backup. SERVER ONLY."""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    bm = get_backup_manager()
    if not bm.is_server_machine():
        return jsonify({'error': 'Restore is only allowed on the Server machine.', 'client_blocked': True}), 403
    data = request.json or {}
    filename = data.get('filename', '').strip()
    if not filename:
        return jsonify({'error': 'filename is required'}), 400
    import posixpath
    # Security: strip any directory traversal attempts
    filename = os.path.basename(filename)
    settings = bm.load_settings()
    filepath = os.path.join(settings.get('backup_folder', ''), filename)
    result = bm.restore_backup(filepath)
    status_code = 200 if result.get('success') else 500
    return jsonify(result), status_code

@app.route('/api/admin/backup/download/<path:filename>')
def api_backup_download(filename):
    """Download a backup .sql file."""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    filename = os.path.basename(filename)  # prevent path traversal
    if not filename.startswith('Maple_Backup_') or not filename.endswith('.sql'):
        return jsonify({'error': 'Invalid filename'}), 400
    bm = get_backup_manager()
    settings = bm.load_settings()
    folder = settings.get('backup_folder', '')
    filepath = os.path.join(folder, filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    from flask import send_file
    return send_file(filepath, as_attachment=True, download_name=filename, mimetype='application/sql')

@app.route('/api/admin/backup/delete', methods=['POST'])
def api_backup_delete():
    """Delete a specific backup file. SERVER ONLY."""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    bm = get_backup_manager()
    if not bm.is_server_machine():
        return jsonify({'error': 'Delete is only allowed on the Server machine.'}), 403
    data = request.json or {}
    filename = os.path.basename(data.get('filename', '').strip())
    result = bm.delete_backup(filename)
    return jsonify(result), (200 if result.get('success') else 400)

@app.route('/api/admin/backup/history')
def api_backup_history():
    """Return backup log history."""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    bm = get_backup_manager()
    return jsonify({'history': bm.get_history(100)})

@app.route('/api/admin/backup/settings', methods=['GET'])
def api_backup_settings_get():
    """Return current backup settings."""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    bm = get_backup_manager()
    settings = bm.load_settings()
    settings['is_server'] = bm.is_server_machine()
    return jsonify(settings)

@app.route('/api/admin/backup/settings', methods=['POST'])
def api_backup_settings_save():
    """Save backup settings."""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    bm = get_backup_manager()
    data = request.json or {}
    allowed_keys = {'backup_folder', 'schedule_interval', 'max_backups', 'auto_backup_enabled'}
    filtered = {k: v for k, v in data.items() if k in allowed_keys}
    try:
        bm.save_settings(filtered)
        return jsonify({'status': 'success', 'message': 'Settings saved.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/admin/backup/schedule/start', methods=['POST'])
def api_backup_schedule_start():
    """Start or change the automatic backup schedule. SERVER ONLY."""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    bm = get_backup_manager()
    if not bm.is_server_machine():
        return jsonify({'error': 'Scheduler only runs on the Server machine.'}), 403
    data = request.json or {}
    interval = data.get('interval')  # optional — reads from settings if not provided
    result = bm.start_scheduler(interval)
    return jsonify(result)

@app.route('/api/admin/backup/schedule/stop', methods=['POST'])
def api_backup_schedule_stop():
    """Stop the automatic backup scheduler."""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    bm = get_backup_manager()
    result = bm.stop_scheduler()
    return jsonify(result)

# ===========================================================================
# END BACKUP SYSTEM ROUTES
# ===========================================================================

import threading
import webbrowser
import time
try:
    import webview
except ImportError:
    webview = None

def run_flask():
    print(f"Starting SocketIO server on {Config.SERVER_HOST}:{Config.SERVER_PORT}...")
    socketio.run(app, host=Config.SERVER_HOST, port=Config.SERVER_PORT, allow_unsafe_werkzeug=True)

if __name__ == '__main__':
    # Auto-create required tables if missing
    try:
        _conn = get_db_connection()
        if _conn:
            _cur = _conn.cursor()
            is_pg = False
            if hasattr(_conn, 'is_pg'):
                is_pg = _conn.is_pg
                
            id_col_def = "id SERIAL PRIMARY KEY" if is_pg else "id INT AUTO_INCREMENT PRIMARY KEY"
            _cur.execute(
                f"CREATE TABLE IF NOT EXISTS stock_transfers ("
                f"  {id_col_def},"
                "  transfer_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
                "  product_barcode VARCHAR(50),"
                "  product_name VARCHAR(255),"
                "  qty DECIMAL(10,2),"
                "  from_location VARCHAR(100),"
                "  to_location VARCHAR(100),"
                "  transfer_type VARCHAR(10) DEFAULT 'OUT',"
                "  pushed_by VARCHAR(100)"
                ")"
            )
            # Add transfer_type column if table existed without it
            try:
                _cur.execute("ALTER TABLE stock_transfers ADD COLUMN transfer_type VARCHAR(10) DEFAULT 'OUT'")
            except:
                pass
            # Add product_barcode column if table existed without it
            try:
                _cur.execute("ALTER TABLE stock_transfers ADD COLUMN product_barcode VARCHAR(50)")
            except:
                pass
            _conn.commit()
            _conn.close()
            print("[Startup] stock_transfers table ready.")
    except Exception as _e:
        print(f"[Startup] Table check skipped: {_e}")

    # Initialize Backup Manager and restore active schedule if enabled
    try:
        _bm = get_backup_manager()
        _bm.auto_start_on_launch()
        print('[Startup] Backup system initialized.')
    except Exception as _bm_err:
        print(f'[Startup] Backup system init skipped: {_bm_err}')

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    host = Config.SERVER_HOST if Config.SERVER_HOST != '0.0.0.0' else '127.0.0.1'
    port = Config.SERVER_PORT
    url = f"http://{host}:{port}/"

    # Wait for the Flask-SocketIO server to start by actively pinging the port
    start_wait = time.time()
    while time.time() - start_wait < 3.0:
        try:
            with socket.create_connection((host, port), timeout=0.1):
                break
        except (socket.timeout, ConnectionRefusedError, OSError):
            time.sleep(0.05)


    try:
        if webview and not os.environ.get("NO_WEBVIEW"):
            print("Launching Desktop Window...")
            webview.create_window("MaplePro Billing System - Sagar Super", url, width=1280, height=800, min_size=(1024, 768))
            webview.start()
        else:
            if not os.environ.get("NO_WEBVIEW"):
                webbrowser.open(url)
            else:
                print("Headless mode: Webview bypassed, server running...")
            while True: time.sleep(100)
    except Exception as e:
        print(f"Webview setup failed: {e}")
        webbrowser.open(url)
        while True: time.sleep(100)
"""  """