import os
import shutil
import glob
from datetime import datetime

def backup():
    import sys
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_dir)
    import config
    db_path = str(config.DB_PATH)
    backup_dir = os.path.join(project_dir, "backups")
    log_file = os.path.join(project_dir, "logs", "backup.log")

    # Ensure directories exist
    os.makedirs(backup_dir, exist_ok=True)
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"nur_trading_{timestamp}.db")

    try:
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found at {db_path}")

        # Copy the database
        shutil.copy2(db_path, backup_path)
        
        # Clean up older backups: keep only last 7
        backup_files = sorted(
            glob.glob(os.path.join(backup_dir, "nur_trading_*.db")),
            key=os.path.getmtime
        )
        deleted_count = 0
        if len(backup_files) > 7:
            for old_backup in backup_files[:-7]:
                os.remove(old_backup)
                deleted_count += 1

        log_msg = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | SUCCESS | Backup created at {backup_path}. Deleted {deleted_count} old backups.\n"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_msg)
        print(f"Backup successful: {backup_path}")
        
    except Exception as e:
        log_msg = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | FAILURE | Error during backup: {str(e)}\n"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_msg)
        print(f"Backup failed: {str(e)}")

if __name__ == "__main__":
    backup()
