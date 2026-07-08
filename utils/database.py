import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS penalties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            reason TEXT,
            proof_url TEXT,
            issued_by INTEGER,
            issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn

def get_balance(user_id: int) -> int:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def set_balance(user_id: int, amount: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (user_id, balance) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET balance = excluded.balance",
        (user_id, amount)
    )
    conn.commit()
    conn.close()

def add_penalty(user_id: int, reason: str, proof_url: str, issued_by: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO penalties (user_id, reason, proof_url, issued_by) VALUES (?, ?, ?, ?)",
        (user_id, reason, proof_url, issued_by)
    )
    conn.commit()
    conn.close()
