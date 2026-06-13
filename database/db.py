"""
database/db.py — SQLite connection manager.

Design decisions:
  - WAL journal mode: allows concurrent reads while a write is happening.
    Critical because bot_engine writes stats while telegram_bot reads them.
  - Thread lock: one write at a time, preventing race conditions.
  - Row factory: rows returned as dict-like sqlite3.Row objects.
  - 30s timeout: prevents indefinite blocking on a locked database.

All other database modules use get_connection() — never open connections directly.
"""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from utils.logger import get_logger

logger = get_logger(__name__)

_LOCK = threading.Lock()
_DB_PATH: Path | None = None


def init_db(db_path: Path) -> None:
    """
    Initialize the database. Call once at startup (from main.py).
    Creates all tables if they don't exist. Safe to call on every startup.
    """
    global _DB_PATH
    _DB_PATH = db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with _raw_conn() as conn:
        # WAL mode: readers don't block writers and vice-versa
        conn.execute("PRAGMA journal_mode=WAL")
        # NORMAL sync: safe on most hardware, much faster than FULL
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _create_schema(conn)

    logger.info(f"Database ready → {db_path}")


def _raw_conn() -> sqlite3.Connection:
    global _DB_PATH
    if _DB_PATH is None:
        import config
        init_db(config.DB_PATH)
    conn = sqlite3.connect(str(_DB_PATH), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Thread-safe write context manager.
    Commits on clean exit, rolls back on any exception.

    Usage:
        with get_connection() as conn:
            conn.execute("UPDATE bot_stats SET wins = wins + 1")
    """
    with _LOCK:
        conn = _raw_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def query_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    """Convenience read — returns first row or None. No lock needed for reads in WAL mode."""
    conn = _raw_conn()
    try:
        cur = conn.execute(sql, params)
        return cur.fetchone()
    finally:
        conn.close()


def _add_column_if_missing(conn: sqlite3.Connection, table_name: str, column_name: str, column_type: str) -> None:
    try:
        conn.execute(f"SELECT {column_name} FROM {table_name} LIMIT 1")
    except sqlite3.OperationalError:
        try:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
            logger.info(f"Added column {column_name} to table {table_name}")
        except Exception as e:
            logger.error(f"Failed to add column {column_name} to table {table_name}: {e}")


def _create_schema(conn: sqlite3.Connection) -> None:
    """Create all tables. Idempotent — safe to run on every startup."""
    # Ensure tables exist (non-destructive)
    conn.executescript("""
        -- Users Table (SaaS Tenants with Auth)
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            email           TEXT,
            password_hash   TEXT,
            display_name    TEXT,
            mt5_login       INTEGER,
            mt5_password    TEXT,
            mt5_server      TEXT DEFAULT 'MetaQuotes-Demo',
            risk_multiplier REAL DEFAULT 1.0,
            is_active       INTEGER DEFAULT 1,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login      TIMESTAMP
        );

        -- Multi-tenant Bot Stats
        CREATE TABLE IF NOT EXISTS bot_stats (
            user_id         INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            total_trades    INTEGER NOT NULL DEFAULT 0,
            today_trades    INTEGER NOT NULL DEFAULT 0,
            wins            INTEGER NOT NULL DEFAULT 0,
            losses          INTEGER NOT NULL DEFAULT 0,
            win_rate        REAL NOT NULL DEFAULT 0.0,
            total_pnl       REAL NOT NULL DEFAULT 0.0,
            today_pnl       REAL NOT NULL DEFAULT 0.0
        );

        -- Multi-tenant Trades
        CREATE TABLE IF NOT EXISTS trades (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER DEFAULT 1 REFERENCES users(id) ON DELETE CASCADE,
            ticket          TEXT,
            trade_id        TEXT,
            direction       TEXT NOT NULL,
            entry_price     REAL NOT NULL,
            exit_price      REAL,
            sl              REAL,
            tp              REAL,
            lot             REAL,
            score           INTEGER,
            pnl             REAL,
            exit_reason     TEXT,
            is_paper        INTEGER NOT NULL DEFAULT 0,
            entry_time      TEXT NOT NULL,
            exit_time       TEXT,
            session         TEXT,
            regime          TEXT
        );

        -- Manual Override Commands
        CREATE TABLE IF NOT EXISTS manual_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT,
            command TEXT,
            asset TEXT,
            direction TEXT,
            reason TEXT,
            created_at TIMESTAMP,
            executed_at TIMESTAMP,
            status TEXT
        );
    """)

    # Ensure all newer schema columns exist
    # Users columns
    _add_column_if_missing(conn, "users", "email", "TEXT UNIQUE")
    _add_column_if_missing(conn, "users", "password_hash", "TEXT")
    _add_column_if_missing(conn, "users", "display_name", "TEXT")
    _add_column_if_missing(conn, "users", "mt5_login", "INTEGER")
    _add_column_if_missing(conn, "users", "mt5_password", "TEXT")
    _add_column_if_missing(conn, "users", "mt5_server", "TEXT DEFAULT 'MetaQuotes-Demo'")
    _add_column_if_missing(conn, "users", "risk_multiplier", "REAL DEFAULT 1.0")
    _add_column_if_missing(conn, "users", "is_active", "INTEGER DEFAULT 1")
    _add_column_if_missing(conn, "users", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    _add_column_if_missing(conn, "users", "last_login", "TIMESTAMP")
    _add_column_if_missing(conn, "users", "google_id", "TEXT")
    _add_column_if_missing(conn, "users", "avatar_url", "TEXT")
    _add_column_if_missing(conn, "users", "auth_provider", "TEXT DEFAULT 'email'")

    # Bot Stats columns
    _add_column_if_missing(conn, "bot_stats", "best_win", "REAL NOT NULL DEFAULT 0.0")
    _add_column_if_missing(conn, "bot_stats", "worst_loss", "REAL NOT NULL DEFAULT 0.0")
    _add_column_if_missing(conn, "bot_stats", "win_streak", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "bot_stats", "loss_streak", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "bot_stats", "max_win_streak", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "bot_stats", "max_loss_streak", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "bot_stats", "avg_win", "REAL NOT NULL DEFAULT 0.0")
    _add_column_if_missing(conn, "bot_stats", "avg_loss", "REAL NOT NULL DEFAULT 0.0")
    _add_column_if_missing(conn, "bot_stats", "gross_win", "REAL NOT NULL DEFAULT 0.0")
    _add_column_if_missing(conn, "bot_stats", "gross_loss", "REAL NOT NULL DEFAULT 0.0")
    _add_column_if_missing(conn, "bot_stats", "trading_locked", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "bot_stats", "last_reset_day", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "bot_stats", "loss_lock_timestamp", "TEXT")

    # Seed a default user for smooth backward compatibility if empty
    cur = conn.execute("SELECT COUNT(*) c FROM users")
    if cur.fetchone()["c"] == 0:
        import config
        import bcrypt
        login = config.MT5_LOGIN if config.MT5_LOGIN else 5051162188
        hashed_password = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode("utf-8")
        conn.execute("""
            INSERT OR IGNORE INTO users (id, email, password_hash, display_name, mt5_login, mt5_password, mt5_server)
            VALUES (1, 'admin@nur.bot', ?, 'Default Admin', ?, ?, ?)
        """, (hashed_password, login, config.MT5_PASSWORD, config.MT5_SERVER))
        conn.execute("INSERT OR IGNORE INTO bot_stats (user_id) VALUES (1)")



# ─── Auth database helpers ────────────────────────────────────

def create_user(email: str, password: str, display_name: str, mt5_login: int, 
                mt5_password: str, mt5_server: str, risk_multiplier: float = 1.0) -> int:
    import bcrypt
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    with get_connection() as conn:
        cur = conn.execute("""
            INSERT INTO users (email, password_hash, display_name, mt5_login, mt5_password, mt5_server, risk_multiplier)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (email.lower().strip(), password_hash, display_name, mt5_login, mt5_password, mt5_server, risk_multiplier))
        user_id = cur.lastrowid
        # Initialize default bot stats for user
        conn.execute("INSERT OR IGNORE INTO bot_stats (user_id) VALUES (?)", (user_id,))
        return user_id


def create_google_user(email: str, display_name: str, google_id: str, avatar_url: str) -> int:
    with get_connection() as conn:
        cur = conn.execute("""
            INSERT INTO users (email, password_hash, display_name, google_id, avatar_url, auth_provider, is_active)
            VALUES (?, '', ?, ?, ?, 'google', 1)
        """, (email.lower().strip(), display_name, google_id, avatar_url))
        user_id = cur.lastrowid
        # Initialize default bot stats for user
        conn.execute("INSERT OR IGNORE INTO bot_stats (user_id) VALUES (?)", (user_id,))
        return user_id


def get_user_by_email(email: str) -> dict | None:
    row = query_one("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),))
    return dict(row) if row else None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    import bcrypt
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def update_last_login(user_id: int) -> None:
    from datetime import datetime
    with get_connection() as conn:
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (datetime.utcnow().isoformat(), user_id))
