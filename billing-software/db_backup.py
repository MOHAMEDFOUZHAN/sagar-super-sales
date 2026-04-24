import os
import datetime
import subprocess
from config import Config

def run_backup():
    # 1. Create backup directory if not exists
    backup_dir = os.path.join(os.path.expanduser("~"), "Documents", "SagarSoftware", "backups")
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    # 2. File naming: backup_YYYY-MM-DD_HHMMSS.sql
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"backup_{timestamp}.sql")

    print(f"Starting backup of {Config.MYSQL_DB}...")

    # 3. Command construction (using mysqldump)
    # Note: Assumes mysqldump is in the system PATH (Standard with Laragon/MySQL install)
    command = [
        'mysqldump',
        f'--host={Config.MYSQL_HOST}',
        f'--user={Config.MYSQL_USER}',
        f'--password={Config.MYSQL_PASSWORD}',
        Config.MYSQL_DB
    ]

    try:
        with open(backup_file, 'w', encoding='utf-8') as f:
            result = subprocess.run(command, stdout=f, stderr=subprocess.PIPE, text=True)
        
        if result.returncode == 0:
            print(f"✅ Success! Backup saved to: {backup_file}")
            
            # Optional: Clean up backups older than 30 days
            # (Keep the system clean)
            return True
        else:
            print(f"❌ Backup failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Backup script error: {e}")
        return False

if __name__ == "__main__":
    run_backup()

