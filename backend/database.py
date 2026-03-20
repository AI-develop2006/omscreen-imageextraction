import sqlite3
import os
import psycopg2
import psycopg2.extras
from datetime import datetime
from urllib.parse import urlparse

DB_FILE = "conversions.db"
DATABASE_URL = os.environ.get("DATABASE_URL")

# Determine placeholder style
P = "%s" if DATABASE_URL else "?"

def get_connection():
    try:
        if DATABASE_URL:
            # Use the URL directly for psycopg2, it's more robust than manual parsing
            return psycopg2.connect(DATABASE_URL)
        return sqlite3.connect(DB_FILE)
    except Exception as e:
        print(f"DATABASE CONNECTION ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise

def init_db():
    conn = get_connection()
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
    # Migration: Add data and user_id columns if they don't exist (SQLite only, Postgres should be initialized correctly)
    if not DATABASE_URL:
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
    conn = get_connection()
    c = conn.cursor()
    c.execute(f"INSERT INTO users (id, username, hashed_password) VALUES ({P}, {P}, {P})", (user_id, username, hashed_password))
    conn.commit()
    conn.close()

def get_user_by_username(username: str):
    conn = get_connection()
    # row_factory replacement for psycopg2
    if DATABASE_URL:
        c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    else:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
    
    q = f"SELECT * FROM users WHERE username = {P}"
    c.execute(q, (username,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def add_conversion(file_id: str, user_id: str, original_filename: str, excel_filename: str, data_json: str):
    conn = get_connection()
    c = conn.cursor()
    created_at = datetime.now().isoformat()
    q = f"INSERT INTO conversions (id, user_id, original_filename, excel_filename, created_at, data) VALUES ({P}, {P}, {P}, {P}, {P}, {P})"
    c.execute(q, (file_id, user_id, original_filename, excel_filename, created_at, data_json))
    conn.commit()
    conn.close()

def get_conversion(file_id: str):
    conn = get_connection()
    if DATABASE_URL:
        c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    else:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
    
    q = f"SELECT * FROM conversions WHERE id = {P}"
    c.execute(q, (file_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def update_conversion_data(file_id: str, data_json: str):
    conn = get_connection()
    c = conn.cursor()
    q = f"UPDATE conversions SET data = {P} WHERE id = {P}"
    c.execute(q, (data_json, file_id))
    conn.commit()
    conn.close()

def get_all_conversions(user_id: str):
    conn = get_connection()
    if DATABASE_URL:
        c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    else:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
    
    q = f"SELECT * FROM conversions WHERE user_id = {P} ORDER BY created_at DESC"
    c.execute(q, (user_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]
