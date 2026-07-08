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
        CREATE TABLE IF NOT EXISTS family (
            user_id INTEGER PRIMARY KEY,
            discord_nick TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS autos (
            plate TEXT PRIMARY KEY,
            model TEXT,
            owner_id INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS warehouse (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            item TEXT,
            quantity INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            reason TEXT,
            proof_url TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            participants TEXT,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            created_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS discipline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            reason TEXT,
            proof_url TEXT,
            issued_by INTEGER,
            issued_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
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

def add_transaction(user_id: int, amount: int, reason: str, proof_url: str = ""):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO transactions (user_id, amount, reason, proof_url) VALUES (?, ?, ?, ?)",
        (user_id, amount, reason, proof_url)
    )
    conn.commit()
    conn.close()

def add_family_member(user_id: int, nick: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO family (user_id, discord_nick) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET discord_nick = excluded.discord_nick",
        (user_id, nick)
    )
    conn.commit()
    conn.close()

def get_family_members():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, discord_nick FROM family")
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_auto(plate: str, model: str, owner_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO autos (plate, model, owner_id) VALUES (?, ?, ?)",
        (plate, model, owner_id)
    )
    conn.commit()
    conn.close()

def remove_auto(plate: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM autos WHERE plate = ?", (plate,))
    conn.commit()
    conn.close()

def get_auto(plate: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM autos WHERE plate = ?", (plate,))
    row = cursor.fetchone()
    conn.close()
    return row

def get_all_autos():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM autos")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_warehouse_item(category: str, item: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT quantity FROM warehouse WHERE category = ? AND item = ?", (category, item))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def set_warehouse_item(category: str, item: str, quantity: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO warehouse (category, item, quantity) VALUES (?, ?, ?) "
        "ON CONFLICT(category, item) DO UPDATE SET quantity = excluded.quantity",
        (category, item, quantity)
    )
    conn.commit()
    conn.close()

def get_all_warehouse():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT category, item, quantity FROM warehouse ORDER BY category, item")
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_contract(name: str, participants: str, amount: int, created_by: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO contracts (name, participants, amount, created_by) VALUES (?, ?, ?, ?)",
        (name, participants, amount, created_by)
    )
    conn.commit()
    return cursor.lastrowid

def get_contract(contract_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contracts WHERE id = ?", (contract_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_contract_status(contract_id: int, status: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE contracts SET status = ? WHERE id = ?", (status, contract_id))
    conn.commit()
    conn.close()

def add_discipline(user_id: int, type: str, reason: str, proof_url: str, issued_by: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO discipline (user_id, type, reason, proof_url, issued_by) VALUES (?, ?, ?, ?, ?)",
        (user_id, type, reason, proof_url, issued_by)
    )
    conn.commit()
    conn.close()

def add_log(user_id: int, action: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO logs (user_id, action) VALUES (?, ?)", (user_id, action))
    conn.commit()
    conn.close()

def get_user_logs(user_id: int, limit: int = 50):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT action, timestamp FROM logs WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
        (user_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows
