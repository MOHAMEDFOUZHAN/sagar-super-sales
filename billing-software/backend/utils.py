# Utils Module Stub
import sqlite3
from config import Config

def get_db_connection():
    conn = sqlite3.connect(Config.DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn
