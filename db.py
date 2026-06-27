import sqlite3
from datetime import datetime

DB_PATH = "cache.db"

def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS analyses (
        url_hash   TEXT PRIMARY KEY,
        url        TEXT,
        comments   TEXT,
        result     TEXT,
        created_at TEXT
    )""")
    con.commit()
    con.close()

def get_cached(url_hash):
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT comments, result FROM analyses WHERE url_hash = ?",
        (url_hash,)
    ).fetchone()
    con.close()
    return row if row else None

def save_cache(url_hash, url, comments, result):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT INTO analyses VALUES (?, ?, ?, ?, ?)",
        (url_hash, url, comments, result, datetime.now().isoformat())
    )
    con.commit()
    con.close()