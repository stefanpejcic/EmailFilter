import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "reputation.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS domain_reputation (
            domain TEXT PRIMARY KEY,
            total_checks INTEGER DEFAULT 0,
            user_marked_spam INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def log_domain_check(domain: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO domain_reputation (domain, total_checks, user_marked_spam)
        VALUES (?, 1, 0)
        ON CONFLICT(domain) DO UPDATE SET total_checks = total_checks + 1
    """, (domain,))
    conn.commit()
    conn.close()

def mark_domain_as_spam(domain: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO domain_reputation (domain, total_checks, user_marked_spam)
        VALUES (?, 0, 1)
        ON CONFLICT(domain) DO UPDATE SET user_marked_spam = user_marked_spam + 1
    """, (domain,))
    conn.commit()
    conn.close()

def get_reputation_penalty(domain: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT total_checks, user_marked_spam FROM domain_reputation WHERE domain = ?", (domain,))
    result = cursor.fetchone()
    conn.close()
    if result:
        total, spam = result
        if total == 0:
            return 0
        spam_ratio = spam / total
        return int(-50 * spam_ratio)
    return 0
