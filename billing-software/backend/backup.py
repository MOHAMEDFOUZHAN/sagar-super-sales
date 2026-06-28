"""
MaplePro Billing Software — Automatic Backup System
====================================================
Server-only backup engine. Clients are blocked at API level.

Author: MaplePro Team
"""

import os
import sys
import json
import sqlite3
import datetime
import subprocess
import threading
import shutil
import time
from typing import Optional

# ---------------------------------------------------------------------------
# Config import — same pattern as app.py
# ---------------------------------------------------------------------------
try:
    from config import Config
except ImportError:
    # Fallback when run standalone
    class Config:
        MYSQL_HOST = '127.0.0.1'
        MYSQL_USER = 'root'
        MYSQL_PASSWORD = ''
        MYSQL_DB = 'maple_pro_db'
        MYSQL_PORT = 3306

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_base_dir() -> str:
    """Return absolute base directory (handles PyInstaller EXE or raw script)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_sqlite_path() -> str:
    return os.path.join(_get_base_dir(), 'self_healing.db')


def _get_settings_path() -> str:
    config_dir = os.path.join(_get_base_dir(), 'Configuration')
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, 'backup_settings.json')


# ---------------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------------
DEFAULT_SETTINGS = {
    'backup_folder': os.path.join(os.path.expanduser('~'), 'Documents', 'Maple Backups'),
    'schedule_interval': 'daily',    # '1h' | '6h' | 'daily' | 'weekly'
    'max_backups': 30,
    'auto_backup_enabled': False,
}

INTERVAL_SECONDS = {
    '1h': 3600,
    '6h': 21600,
    'daily': 86400,
    'weekly': 604800,
}

INTERVAL_LABELS = {
    '1h': 'Every 1 Hour',
    '6h': 'Every 6 Hours',
    'daily': 'Daily',
    'weekly': 'Weekly',
}

# ---------------------------------------------------------------------------
# BackupManager
# ---------------------------------------------------------------------------

class BackupManager:
    """
    Central backup manager. Instantiate once at app startup (singleton pattern).
    The manager is server-aware: all destructive methods check is_server_machine()
    and raise PermissionError if called from a client context.
    """

    _instance: Optional['BackupManager'] = None
    _lock = threading.Lock()

    def __init__(self):
        self._scheduler_timer: Optional[threading.Timer] = None
        self._scheduler_lock = threading.Lock()
        self._next_scheduled_time: Optional[datetime.datetime] = None
        self._is_scheduler_running = False
        self._init_sqlite()

    # ------------------------------------------------------------------
    # Server / Client detection
    # ------------------------------------------------------------------

    @staticmethod
    def is_server_machine() -> bool:
        """
        Returns True if this machine IS the database server
        (MySQL is running locally at 127.0.0.1 / localhost).
        Client PCs connect to a remote IP and therefore return False.
        """
        host = getattr(Config, 'MYSQL_HOST', '127.0.0.1').strip().lower()
        return host in ('127.0.0.1', 'localhost', '::1')

    # ------------------------------------------------------------------
    # SQLite history table init
    # ------------------------------------------------------------------

    def _init_sqlite(self):
        """Ensure backup_history table exists in self_healing.db."""
        try:
            conn = sqlite3.connect(_get_sqlite_path())
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backup_history (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    backup_name TEXT NOT NULL,
                    backup_date TEXT,
                    backup_time TEXT,
                    size_bytes  INTEGER DEFAULT 0,
                    backup_type TEXT DEFAULT 'Manual',
                    status      TEXT DEFAULT 'Unknown',
                    duration_sec REAL DEFAULT 0,
                    error_msg   TEXT DEFAULT '',
                    location    TEXT DEFAULT '',
                    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f'[BackupManager] SQLite init error: {e}')

    def _log_history(self, name: str, size_bytes: int, backup_type: str,
                     status: str, duration_sec: float, error_msg: str,
                     location: str):
        """Insert a backup history record into SQLite."""
        try:
            now = datetime.datetime.now()
            conn = sqlite3.connect(_get_sqlite_path())
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO backup_history
                    (backup_name, backup_date, backup_time, size_bytes,
                     backup_type, status, duration_sec, error_msg, location)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                name,
                now.strftime('%Y-%m-%d'),
                now.strftime('%H:%M:%S'),
                size_bytes,
                backup_type,
                status,
                round(duration_sec, 2),
                error_msg,
                location
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f'[BackupManager] History log error: {e}')

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def load_settings(self) -> dict:
        """Load backup settings from Configuration/backup_settings.json."""
        path = _get_settings_path()
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # Merge with defaults to handle missing keys
                merged = dict(DEFAULT_SETTINGS)
                merged.update(data)
                return merged
        except Exception as e:
            print(f'[BackupManager] Settings load error: {e}')
        return dict(DEFAULT_SETTINGS)

    def save_settings(self, settings: dict):
        """Save backup settings to disk."""
        path = _get_settings_path()
        try:
            current = self.load_settings()
            current.update(settings)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(current, f, indent=4)
        except Exception as e:
            print(f'[BackupManager] Settings save error: {e}')
            raise

    # ------------------------------------------------------------------
    # mysqldump path detection
    # ------------------------------------------------------------------

    @staticmethod
    def _find_mysqldump() -> str:
        """
        Find mysqldump executable. Checks Laragon paths, then PATH.
        Returns the path string or 'mysqldump' (relies on PATH).
        """
        # Common Laragon locations
        candidates = [
            r'D:\laragon\bin\mysql\mysql-8.0.30-winx64\bin\mysqldump.exe',
            r'D:\laragon\bin\mysql\mysql-8.0.36-winx64\bin\mysqldump.exe',
            r'C:\laragon\bin\mysql\mysql-8.0.30-winx64\bin\mysqldump.exe',
            r'C:\laragon\bin\mysql\mysql-8.0.36-winx64\bin\mysqldump.exe',
        ]
        # Also check any mysql- version in D:\laragon\bin\mysql\
        for laragon_base in [r'D:\laragon\bin\mysql', r'C:\laragon\bin\mysql']:
            if os.path.isdir(laragon_base):
                for entry in os.listdir(laragon_base):
                    candidate = os.path.join(laragon_base, entry, 'bin', 'mysqldump.exe')
                    if os.path.isfile(candidate):
                        return candidate

        for path in candidates:
            if os.path.isfile(path):
                return path

        return 'mysqldump'  # Fall back to PATH

    @staticmethod
    def _find_mysql_cli() -> str:
        """Find mysql CLI executable for restores."""
        for laragon_base in [r'D:\laragon\bin\mysql', r'C:\laragon\bin\mysql']:
            if os.path.isdir(laragon_base):
                for entry in os.listdir(laragon_base):
                    candidate = os.path.join(laragon_base, entry, 'bin', 'mysql.exe')
                    if os.path.isfile(candidate):
                        return candidate
        return 'mysql'

    # ------------------------------------------------------------------
    # Backup creation
    # ------------------------------------------------------------------

    def create_backup(self, backup_type: str = 'Manual') -> dict:
        """
        Create a MySQL dump backup. SERVER ONLY.
        Returns dict: {success, name, path, size_bytes, duration_sec, error}
        """
        if not self.is_server_machine():
            return {
                'success': False,
                'error': 'Backup creation is only allowed on the Server machine.',
                'client_blocked': True
            }

        settings = self.load_settings()
        backup_folder = settings.get('backup_folder', DEFAULT_SETTINGS['backup_folder'])

        # Ensure backup folder exists
        try:
            os.makedirs(backup_folder, exist_ok=True)
        except Exception as e:
            return {'success': False, 'error': f'Cannot create backup folder: {e}'}

        # Generate filename
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        filename = f'Maple_Backup_{timestamp}.sql'
        filepath = os.path.join(backup_folder, filename)

        mysqldump = self._find_mysqldump()

        # Build mysqldump command — safe, non-locking, consistent snapshot
        cmd = [
            mysqldump,
            f'--host={Config.MYSQL_HOST}',
            f'--port={Config.MYSQL_PORT}',
            f'--user={Config.MYSQL_USER}',
            '--single-transaction',      # InnoDB consistent snapshot; no global lock
            '--lock-tables=false',       # Never lock all tables globally
            '--routines',                # Include stored routines
            '--triggers',                # Include triggers
            '--add-drop-table',          # Safe for restore (drops existing tables)
            '--set-charset',
            '--default-character-set=utf8mb4',
        ]
        # Add password only if set (avoid empty --password= warning)
        if Config.MYSQL_PASSWORD:
            cmd.append(f'--password={Config.MYSQL_PASSWORD}')

        cmd.append(Config.MYSQL_DB)

        start_time = time.time()
        error_msg = ''
        size_bytes = 0

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=300  # 5 min max
                )

            duration_sec = time.time() - start_time

            if result.returncode != 0:
                stderr_text = result.stderr.strip()
                # mysqldump often prints warnings to stderr even on success
                # Treat as error only if returncode != 0
                error_msg = stderr_text or f'mysqldump exited with code {result.returncode}'
                # Clean up failed file
                if os.path.exists(filepath):
                    os.remove(filepath)
                self._log_history(filename, 0, backup_type, 'Failed', duration_sec, error_msg, backup_folder)
                return {'success': False, 'error': error_msg, 'duration_sec': duration_sec}

            # Verify backup
            verify = self.verify_backup(filepath)
            if not verify['valid']:
                error_msg = verify['reason']
                if os.path.exists(filepath):
                    os.remove(filepath)
                self._log_history(filename, 0, backup_type, 'Failed', duration_sec, error_msg, backup_folder)
                return {'success': False, 'error': error_msg, 'duration_sec': duration_sec}

            size_bytes = os.path.getsize(filepath)

            # Cleanup old backups
            self.cleanup_old_backups(backup_folder, settings.get('max_backups', 30))

            self._log_history(filename, size_bytes, backup_type, 'Success', duration_sec, '', backup_folder)
            print(f'[BackupManager] Backup created: {filepath} ({self._human_size(size_bytes)}) in {duration_sec:.1f}s')

            return {
                'success': True,
                'name': filename,
                'path': filepath,
                'size_bytes': size_bytes,
                'size_human': self._human_size(size_bytes),
                'duration_sec': round(duration_sec, 2),
                'error': ''
            }

        except subprocess.TimeoutExpired:
            duration_sec = time.time() - start_time
            error_msg = 'mysqldump timed out after 5 minutes.'
            if os.path.exists(filepath):
                os.remove(filepath)
            self._log_history(filename, 0, backup_type, 'Failed', duration_sec, error_msg, backup_folder)
            return {'success': False, 'error': error_msg, 'duration_sec': duration_sec}

        except FileNotFoundError:
            duration_sec = time.time() - start_time
            error_msg = (
                f'mysqldump not found. Make sure Laragon/MySQL is installed and '
                f'mysqldump.exe is accessible. Tried: {mysqldump}'
            )
            self._log_history(filename, 0, backup_type, 'Failed', duration_sec, error_msg, backup_folder)
            return {'success': False, 'error': error_msg}

        except Exception as e:
            duration_sec = time.time() - start_time
            error_msg = str(e)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
            self._log_history(filename, 0, backup_type, 'Failed', duration_sec, error_msg, backup_folder)
            return {'success': False, 'error': error_msg}

    # ------------------------------------------------------------------
    # Backup verification
    # ------------------------------------------------------------------

    @staticmethod
    def verify_backup(filepath: str) -> dict:
        """
        Verify a backup file:
        - exists on disk
        - size > 0
        - contains at least some SQL content
        Returns {valid: bool, reason: str}
        """
        if not os.path.exists(filepath):
            return {'valid': False, 'reason': 'Backup file does not exist on disk.'}
        size = os.path.getsize(filepath)
        if size == 0:
            return {'valid': False, 'reason': 'Backup file is empty (0 bytes).'}
        # Quick check — read first 512 bytes to confirm it's a SQL dump
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                header = f.read(512)
            if not any(kw in header.lower() for kw in ['mysql', 'dump', 'create', 'insert', '--']):
                return {'valid': False, 'reason': 'File does not appear to be a valid SQL dump.'}
        except Exception as e:
            return {'valid': False, 'reason': f'Could not read backup file: {e}'}
        return {'valid': True, 'reason': ''}

    # ------------------------------------------------------------------
    # Cleanup old backups
    # ------------------------------------------------------------------

    @staticmethod
    def cleanup_old_backups(backup_folder: str, max_backups: int = 30):
        """
        Keep only the newest `max_backups` SQL files.
        Deletes oldest files first. Never deletes the newest.
        """
        try:
            files = [
                os.path.join(backup_folder, f)
                for f in os.listdir(backup_folder)
                if f.lower().endswith('.sql') and f.startswith('Maple_Backup_')
            ]
            if len(files) <= max_backups:
                return
            # Sort by modification time (oldest first)
            files.sort(key=lambda p: os.path.getmtime(p))
            to_delete = files[:len(files) - max_backups]
            for f in to_delete:
                try:
                    os.remove(f)
                    print(f'[BackupManager] Deleted old backup: {os.path.basename(f)}')
                except Exception as e:
                    print(f'[BackupManager] Could not delete {f}: {e}')
        except Exception as e:
            print(f'[BackupManager] Cleanup error: {e}')

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------

    def restore_backup(self, filepath: str) -> dict:
        """
        Restore a backup file into the database. SERVER ONLY.
        Automatically creates a safety backup before restoring.
        """
        if not self.is_server_machine():
            return {
                'success': False,
                'error': 'Restore is only allowed on the Server machine.',
                'client_blocked': True
            }

        if not os.path.exists(filepath):
            return {'success': False, 'error': 'Backup file not found.'}

        verify = self.verify_backup(filepath)
        if not verify['valid']:
            return {'success': False, 'error': f'Backup verification failed: {verify["reason"]}'}

        # Safety backup before restore
        print('[BackupManager] Creating safety backup before restore...')
        safety = self.create_backup(backup_type='Safety (Pre-Restore)')
        if not safety.get('success'):
            return {
                'success': False,
                'error': f'Could not create safety backup before restore: {safety.get("error")}'
            }

        mysql_cli = self._find_mysql_cli()
        cmd = [
            mysql_cli,
            f'--host={Config.MYSQL_HOST}',
            f'--port={Config.MYSQL_PORT}',
            f'--user={Config.MYSQL_USER}',
            Config.MYSQL_DB
        ]
        if Config.MYSQL_PASSWORD:
            cmd.append(f'--password={Config.MYSQL_PASSWORD}')

        start_time = time.time()
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                result = subprocess.run(
                    cmd,
                    stdin=f,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=600
                )

            duration_sec = time.time() - start_time

            if result.returncode != 0:
                err = result.stderr.strip() or f'mysql exited with code {result.returncode}'
                return {'success': False, 'error': err, 'duration_sec': round(duration_sec, 2)}

            print(f'[BackupManager] Restore complete from {os.path.basename(filepath)}')
            return {
                'success': True,
                'message': f'Database restored from {os.path.basename(filepath)}.',
                'safety_backup': os.path.basename(safety.get('path', '')),
                'duration_sec': round(duration_sec, 2)
            }

        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Restore timed out after 10 minutes.'}
        except FileNotFoundError:
            return {
                'success': False,
                'error': f'mysql CLI not found. Tried: {mysql_cli}. Ensure Laragon/MySQL is installed.'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ------------------------------------------------------------------
    # List backups
    # ------------------------------------------------------------------

    def get_backup_list(self) -> list:
        """Return list of backup dicts sorted newest-first."""
        settings = self.load_settings()
        folder = settings.get('backup_folder', DEFAULT_SETTINGS['backup_folder'])
        results = []

        if not os.path.isdir(folder):
            return results

        for fname in sorted(os.listdir(folder), reverse=True):
            if not (fname.lower().endswith('.sql') and fname.startswith('Maple_Backup_')):
                continue
            fpath = os.path.join(folder, fname)
            try:
                stat = os.stat(fpath)
                mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
                size_bytes = stat.st_size
                results.append({
                    'name': fname,
                    'path': fpath,
                    'date': mtime.strftime('%Y-%m-%d'),
                    'time': mtime.strftime('%H:%M:%S'),
                    'size_bytes': size_bytes,
                    'size_human': self._human_size(size_bytes),
                    'location': folder,
                    'valid': size_bytes > 0,
                })
            except Exception:
                continue

        return results

    # ------------------------------------------------------------------
    # Backup history from SQLite
    # ------------------------------------------------------------------

    def get_history(self, limit: int = 100) -> list:
        """Return backup history records newest-first."""
        try:
            conn = sqlite3.connect(_get_sqlite_path())
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, backup_name, backup_date, backup_time, size_bytes,
                       backup_type, status, duration_sec, error_msg, location, created_at
                FROM backup_history
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            print(f'[BackupManager] History read error: {e}')
            return []

    # ------------------------------------------------------------------
    # Delete a backup
    # ------------------------------------------------------------------

    def delete_backup(self, filename: str) -> dict:
        """Delete a specific backup file. SERVER ONLY."""
        if not self.is_server_machine():
            return {'success': False, 'error': 'Delete is only allowed on the Server machine.'}

        settings = self.load_settings()
        folder = settings.get('backup_folder', DEFAULT_SETTINGS['backup_folder'])
        filepath = os.path.join(folder, filename)

        # Safety: only allow deleting Maple_Backup_*.sql files inside backup folder
        if not filename.startswith('Maple_Backup_') or not filename.endswith('.sql'):
            return {'success': False, 'error': 'Invalid backup filename.'}

        if not os.path.exists(filepath):
            return {'success': False, 'error': 'File not found.'}

        try:
            os.remove(filepath)
            return {'success': True, 'message': f'Deleted {filename}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ------------------------------------------------------------------
    # Scheduler
    # ------------------------------------------------------------------

    def start_scheduler(self, interval: Optional[str] = None) -> dict:
        """
        Start the automatic backup scheduler. SERVER ONLY.
        interval: '1h' | '6h' | 'daily' | 'weekly' (reads from settings if None)
        """
        if not self.is_server_machine():
            return {'success': False, 'error': 'Scheduler only runs on the Server machine.'}

        settings = self.load_settings()
        if interval:
            settings['schedule_interval'] = interval
            settings['auto_backup_enabled'] = True
            self.save_settings(settings)
        else:
            interval = settings.get('schedule_interval', 'daily')

        seconds = INTERVAL_SECONDS.get(interval, 86400)

        with self._scheduler_lock:
            self._cancel_timer()
            self._is_scheduler_running = True
            self._schedule_next(seconds)

        label = INTERVAL_LABELS.get(interval, interval)
        print(f'[BackupManager] Scheduler started: {label} (every {seconds}s)')
        return {'success': True, 'message': f'Scheduler started: {label}', 'interval': interval}

    def stop_scheduler(self) -> dict:
        """Stop the automatic backup scheduler."""
        with self._scheduler_lock:
            self._cancel_timer()
            self._is_scheduler_running = False
            self._next_scheduled_time = None

        settings = self.load_settings()
        settings['auto_backup_enabled'] = False
        self.save_settings(settings)
        print('[BackupManager] Scheduler stopped.')
        return {'success': True, 'message': 'Scheduler stopped.'}

    def _schedule_next(self, seconds: int):
        """Schedule the next backup after `seconds`."""
        self._next_scheduled_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        self._scheduler_timer = threading.Timer(seconds, self._run_scheduled_backup, args=[seconds])
        self._scheduler_timer.daemon = True
        self._scheduler_timer.start()

    def _run_scheduled_backup(self, seconds: int):
        """Execute the scheduled backup then re-arm for the next cycle."""
        print('[BackupManager] Running scheduled automatic backup...')
        result = self.create_backup(backup_type='Automatic')
        if result.get('success'):
            print(f'[BackupManager] Scheduled backup complete: {result.get("name")}')
        else:
            print(f'[BackupManager] Scheduled backup failed: {result.get("error")}')

        # Re-arm if still running
        with self._scheduler_lock:
            if self._is_scheduler_running:
                self._schedule_next(seconds)

    def _cancel_timer(self):
        """Cancel the active timer (must be called within _scheduler_lock)."""
        if self._scheduler_timer and self._scheduler_timer.is_alive():
            self._scheduler_timer.cancel()
        self._scheduler_timer = None

    def get_scheduler_status(self) -> dict:
        """Return current scheduler status."""
        settings = self.load_settings()
        interval = settings.get('schedule_interval', 'daily')
        enabled = settings.get('auto_backup_enabled', False)

        next_time_str = None
        if self._next_scheduled_time and self._is_scheduler_running:
            next_time_str = self._next_scheduled_time.strftime('%d-%m-%Y %I:%M:%S %p')

        return {
            'is_running': self._is_scheduler_running,
            'interval': interval,
            'interval_label': INTERVAL_LABELS.get(interval, interval),
            'next_scheduled': next_time_str,
            'auto_enabled': enabled,
        }

    # ------------------------------------------------------------------
    # Auto-start on server launch
    # ------------------------------------------------------------------

    def auto_start_on_launch(self):
        """
        Called at server startup. If auto_backup_enabled is True in settings,
        re-arm the scheduler. Safe no-op on client machines.
        """
        if not self.is_server_machine():
            return
        settings = self.load_settings()
        if settings.get('auto_backup_enabled', False):
            interval = settings.get('schedule_interval', 'daily')
            print(f'[BackupManager] Restoring scheduler on startup: {INTERVAL_LABELS.get(interval, interval)}')
            self.start_scheduler(interval)
        else:
            print('[BackupManager] Auto-backup is disabled. Scheduler not started.')

    # ------------------------------------------------------------------
    # Dashboard status summary
    # ------------------------------------------------------------------

    def get_status_summary(self) -> dict:
        """Return a quick status dict for the dashboard card."""
        backup_list = self.get_backup_list()
        scheduler = self.get_scheduler_status()
        settings = self.load_settings()

        last_backup = None
        if backup_list:
            lb = backup_list[0]
            last_backup = {
                'name': lb['name'],
                'date': lb['date'],
                'time': lb['time'],
                'size_human': lb['size_human'],
            }

        return {
            'is_server': self.is_server_machine(),
            'last_backup': last_backup,
            'next_scheduled': scheduler.get('next_scheduled'),
            'scheduler_running': scheduler.get('is_running', False),
            'auto_enabled': scheduler.get('auto_enabled', False),
            'interval_label': scheduler.get('interval_label', '—'),
            'total_backups': len(backup_list),
            'max_backups': settings.get('max_backups', 30),
            'backup_folder': settings.get('backup_folder', ''),
        }

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _human_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f'{size_bytes} B'
        elif size_bytes < 1024 ** 2:
            return f'{size_bytes / 1024:.1f} KB'
        elif size_bytes < 1024 ** 3:
            return f'{size_bytes / (1024 ** 2):.2f} MB'
        return f'{size_bytes / (1024 ** 3):.2f} GB'


# ---------------------------------------------------------------------------
# Module-level singleton accessor
# ---------------------------------------------------------------------------
_backup_manager_instance: Optional[BackupManager] = None
_bm_lock = threading.Lock()


def get_backup_manager() -> BackupManager:
    """Return the singleton BackupManager instance."""
    global _backup_manager_instance
    if _backup_manager_instance is None:
        with _bm_lock:
            if _backup_manager_instance is None:
                _backup_manager_instance = BackupManager()
    return _backup_manager_instance
