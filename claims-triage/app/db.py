"""SQLite persistence layer for claim submissions."""
import json
import os
import sqlite3
from pathlib import Path


def _db_path():
    return Path(os.environ.get("DATABASE_PATH", "claims.db"))


def get_db_connection():
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db(app):
    with app.app_context():
        conn = get_db_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                submitted_at TEXT    NOT NULL DEFAULT (datetime('now')),
                claim_text   TEXT    NOT NULL,
                claim_type   TEXT,
                amount_band  TEXT,
                amount_sgd   REAL,
                result_json  TEXT    NOT NULL
            )
        """)
        conn.commit()
        conn.close()


def save_claim(claim_text, claim_type, amount_band, amount_sgd, result):
    conn = get_db_connection()
    cur = conn.execute(
        """INSERT INTO claims (claim_text, claim_type, amount_band, amount_sgd, result_json)
           VALUES (?, ?, ?, ?, ?)""",
        (claim_text, claim_type, amount_band, amount_sgd, json.dumps(result)),
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_claim(row_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM claims WHERE id = ?", (row_id,)).fetchone()
    conn.close()
    return row


def get_all_claims():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM claims ORDER BY submitted_at DESC"
    ).fetchall()
    conn.close()
    return rows
