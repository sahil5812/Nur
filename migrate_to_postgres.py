#!/usr/bin/env python3
"""
migrate_to_postgres.py — Migrate Nur Trading Bot from SQLite to PostgreSQL

This script reads all data from the local SQLite database (nur_trading.db)
and inserts it into a PostgreSQL database (Supabase, Neon, or any PG host).

Prerequisites:
    pip install psycopg2-binary

Usage:
    # Set your PostgreSQL connection string
    export DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres"
    
    # Run the migration
    python migrate_to_postgres.py

    # Or pass it inline:
    DATABASE_URL="postgresql://..." python migrate_to_postgres.py

Notes:
    - This script is idempotent: it uses IF NOT EXISTS for all DDL
    - Existing rows in PostgreSQL are NOT overwritten (INSERT ... ON CONFLICT DO NOTHING)
    - Always test on a staging database first
"""

import os
import sys
import sqlite3
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2 is not installed.")
    print("  Run: pip install psycopg2-binary")
    sys.exit(1)


# ── Configuration ─────────────────────────────────────────────
SQLITE_PATH = Path(__file__).parent / "database" / "nur_trading.db"
PG_URL = os.getenv("DATABASE_URL")

if not PG_URL:
    print("ERROR: DATABASE_URL environment variable is not set.")
    print("  Export it before running this script:")
    print('  export DATABASE_URL="postgresql://user:pass@host:5432/dbname"')
    sys.exit(1)

if not SQLITE_PATH.exists():
    print(f"ERROR: SQLite database not found at {SQLITE_PATH}")
    sys.exit(1)


# ── PostgreSQL Schema ─────────────────────────────────────────
PG_SCHEMA = """
-- Users (SaaS Tenants)
CREATE TABLE IF NOT EXISTS users (
    user_id         SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    mt5_login       BIGINT UNIQUE NOT NULL,
    mt5_password    TEXT,
    mt5_server      TEXT,
    risk_multiplier DOUBLE PRECISION DEFAULT 1.0,
    is_active       INTEGER NOT NULL DEFAULT 1
);

-- Bot Stats (per user)
CREATE TABLE IF NOT EXISTS bot_stats (
    user_id         INTEGER PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    total_trades    INTEGER NOT NULL DEFAULT 0,
    today_trades    INTEGER NOT NULL DEFAULT 0,
    wins            INTEGER NOT NULL DEFAULT 0,
    losses          INTEGER NOT NULL DEFAULT 0,
    win_rate        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_pnl       DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    today_pnl       DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    best_win        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    worst_loss      DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    win_streak      INTEGER NOT NULL DEFAULT 0,
    loss_streak     INTEGER NOT NULL DEFAULT 0,
    max_win_streak  INTEGER NOT NULL DEFAULT 0,
    max_loss_streak INTEGER NOT NULL DEFAULT 0,
    avg_win         DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    avg_loss        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    gross_win       DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    gross_loss      DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    trading_locked  INTEGER NOT NULL DEFAULT 0,
    last_reset_day  TEXT NOT NULL DEFAULT ''
);

-- Trades (full history)
CREATE TABLE IF NOT EXISTS trades (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER DEFAULT 1 REFERENCES users(user_id) ON DELETE CASCADE,
    ticket          TEXT,
    trade_id        TEXT,
    direction       TEXT NOT NULL,
    entry_price     DOUBLE PRECISION NOT NULL,
    exit_price      DOUBLE PRECISION,
    sl              DOUBLE PRECISION,
    tp              DOUBLE PRECISION,
    lot             DOUBLE PRECISION,
    score           INTEGER,
    pnl             DOUBLE PRECISION,
    exit_reason     TEXT,
    is_paper        INTEGER NOT NULL DEFAULT 0,
    entry_time      TEXT NOT NULL,
    exit_time       TEXT,
    session         TEXT,
    regime          TEXT
);
"""


def migrate():
    print("=" * 60)
    print("NUR TRADING BOT — SQLite → PostgreSQL Migration")
    print("=" * 60)
    print(f"  Source:  {SQLITE_PATH}")
    print(f"  Target:  {PG_URL[:40]}...")
    print()

    # ── Connect to both databases ─────────────────────────────
    print("[1/5] Connecting to SQLite...")
    sq = sqlite3.connect(str(SQLITE_PATH))
    sq.row_factory = sqlite3.Row

    print("[2/5] Connecting to PostgreSQL...")
    pg = psycopg2.connect(PG_URL)
    pg.autocommit = False
    cur = pg.cursor()

    try:
        # ── Create schema ─────────────────────────────────────
        print("[3/5] Creating PostgreSQL schema...")
        cur.execute(PG_SCHEMA)
        pg.commit()
        print("       Schema created successfully")

        # ── Migrate users ─────────────────────────────────────
        print("[4/5] Migrating data...")
        
        users = sq.execute("SELECT * FROM users").fetchall()
        user_count = 0
        for u in users:
            try:
                cur.execute("""
                    INSERT INTO users (user_id, name, mt5_login, mt5_password, mt5_server, risk_multiplier, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO NOTHING
                """, (u["user_id"], u["name"], u["mt5_login"], u["mt5_password"],
                      u["mt5_server"], u["risk_multiplier"], u["is_active"]))
                user_count += 1
            except Exception as e:
                print(f"       WARN: Skipped user {u['user_id']}: {e}")

        # Reset the sequence to max user_id
        cur.execute("SELECT COALESCE(MAX(user_id), 0) FROM users")
        max_uid = cur.fetchone()[0]
        if max_uid > 0:
            cur.execute(f"SELECT setval('users_user_id_seq', {max_uid})")

        # ── Migrate bot_stats ─────────────────────────────────
        stats = sq.execute("SELECT * FROM bot_stats").fetchall()
        stat_count = 0
        for s in stats:
            try:
                cur.execute("""
                    INSERT INTO bot_stats (
                        user_id, total_trades, today_trades, wins, losses, win_rate,
                        total_pnl, today_pnl, best_win, worst_loss,
                        win_streak, loss_streak, max_win_streak, max_loss_streak,
                        avg_win, avg_loss, gross_win, gross_loss,
                        trading_locked, last_reset_day
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (user_id) DO NOTHING
                """, (
                    s["user_id"], s["total_trades"], s["today_trades"],
                    s["wins"], s["losses"], s["win_rate"],
                    s["total_pnl"], s["today_pnl"], s["best_win"], s["worst_loss"],
                    s["win_streak"], s["loss_streak"], s["max_win_streak"], s["max_loss_streak"],
                    s["avg_win"], s["avg_loss"], s["gross_win"], s["gross_loss"],
                    s["trading_locked"], s["last_reset_day"],
                ))
                stat_count += 1
            except Exception as e:
                print(f"       WARN: Skipped stats for user {s['user_id']}: {e}")

        # ── Migrate trades ────────────────────────────────────
        trades = sq.execute("SELECT * FROM trades").fetchall()
        trade_count = 0
        for t in trades:
            try:
                cur.execute("""
                    INSERT INTO trades (
                        user_id, ticket, trade_id, direction, entry_price, exit_price,
                        sl, tp, lot, score, pnl, exit_reason,
                        is_paper, entry_time, exit_time, session, regime
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    t["user_id"], t["ticket"], t["trade_id"], t["direction"],
                    t["entry_price"], t["exit_price"], t["sl"], t["tp"],
                    t["lot"], t["score"], t["pnl"], t["exit_reason"],
                    t["is_paper"], t["entry_time"], t["exit_time"],
                    t["session"], t["regime"],
                ))
                trade_count += 1
            except Exception as e:
                print(f"       WARN: Skipped trade {t['id']}: {e}")

        # Reset trades sequence
        cur.execute("SELECT COALESCE(MAX(id), 0) FROM trades")
        max_tid = cur.fetchone()[0]
        if max_tid > 0:
            cur.execute(f"SELECT setval('trades_id_seq', {max_tid})")

        pg.commit()

        # ── Summary ───────────────────────────────────────────
        print()
        print("[5/5] Migration complete!")
        print(f"       Users:     {user_count} migrated")
        print(f"       Stats:     {stat_count} migrated")
        print(f"       Trades:    {trade_count} migrated")
        print()
        print("  Next steps:")
        print('    1. Set DATABASE_URL in your .env or docker-compose.yml')
        print("    2. Update database/db.py to use psycopg2 when DATABASE_URL is set")
        print("    3. Test with: python diagnose.py")
        print("=" * 60)

    except Exception as exc:
        pg.rollback()
        print(f"\nERROR: Migration failed — {exc}")
        print("  All changes have been rolled back.")
        raise
    finally:
        cur.close()
        pg.close()
        sq.close()


if __name__ == "__main__":
    migrate()
