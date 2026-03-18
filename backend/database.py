import sqlite3
import os
from datetime import datetime

DB_FILE = "conversions.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE,
            hashed_password TEXT
        )
    ''')
    # Conversions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversions (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            original_filename TEXT,
            excel_filename TEXT,
            created_at TEXT,
            data TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    # Migration: Add data and user_id columns if they don't exist
    try:
        c.execute("ALTER TABLE conversions ADD COLUMN data TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE conversions ADD COLUMN user_id TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def add_user(user_id: str, username: str, hashed_password: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO users (id, username, hashed_password) VALUES (?, ?, ?)", (user_id, username, hashed_password))
    conn.commit()
    conn.close()

def get_user_by_username(username: str):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def add_conversion(file_id: str, user_id: str, original_filename: str, excel_filename: str, data_json: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    created_at = datetime.now().isoformat()
    c.execute(
        "INSERT INTO conversions (id, user_id, original_filename, excel_filename, created_at, data) VALUES (?, ?, ?, ?, ?, ?)",
        (file_id, user_id, original_filename, excel_filename, created_at, data_json)
    )
    conn.commit()
    conn.close()

def get_conversion(file_id: str):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM conversions WHERE id = ?", (file_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def update_conversion_data(file_id: str, data_json: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE conversions SET data = ? WHERE id = ?", (data_json, file_id))
    conn.commit()
    conn.close()

def get_all_conversions(user_id: str):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM conversions WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]
