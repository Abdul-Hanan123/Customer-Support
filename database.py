"""
database.py
Handles all SQLite operations: users, chat history, feedback, and
knowledge-base entry metadata (the raw text KB lives here; embeddings
live in the FAISS index built by rag_pipeline.py).
"""

import sqlite3
import bcrypt
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "app.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all tables if they don't exist, and seed a default admin."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,          -- 'user' or 'assistant'
            message TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            rating TEXT NOT NULL,        -- 'like' or 'dislike'
            timestamp TEXT NOT NULL,
            FOREIGN KEY (chat_id) REFERENCES chat_history(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS kb_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'manual',  -- manual / pdf / url
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS faqs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL
        )
    """)

    conn.commit()

    # Seed default admin if no users exist
    cur.execute("SELECT COUNT(*) as c FROM users")
    if cur.fetchone()["c"] == 0:
        admin_user = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
        admin_pass = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
        create_user(admin_user, admin_pass, role="admin")

    # Seed a couple of FAQs so the section isn't empty on first run
    cur.execute("SELECT COUNT(*) as c FROM faqs")
    if cur.fetchone()["c"] == 0:
        seed_faqs = [
            ("What is this chatbot for?",
             "It answers questions using our company knowledge base."),
            ("How do I contact a human agent?",
             "Ask the bot to 'connect me to support' or email support@company.com."),
            ("Can I export my chat history?",
             "Yes — use the 'Export Chat History' button in the chat sidebar."),
        ]
        cur.executemany("INSERT INTO faqs (question, answer) VALUES (?, ?)", seed_faqs)
        conn.commit()

    conn.close()


# ---------- USERS ----------

def create_user(username, password, role="user"):
    conn = get_connection()
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (username, hashed, role, datetime.utcnow().isoformat())
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def verify_user(username, password):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if row and bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
        return {"id": row["id"], "username": row["username"], "role": row["role"]}
    return None


# ---------- CHAT HISTORY ----------

def save_message(user_id, session_id, role, message):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO chat_history (user_id, session_id, role, message, timestamp) VALUES (?, ?, ?, ?, ?)",
        (user_id, session_id, role, message, datetime.utcnow().isoformat())
    )
    conn.commit()
    chat_id = cur.lastrowid
    conn.close()
    return chat_id


def get_session_history(user_id, session_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM chat_history WHERE user_id = ? AND session_id = ? ORDER BY id ASC",
        (user_id, session_id)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_sessions(user_id):
    conn = get_connection()
    rows = conn.execute(
        """SELECT session_id, MIN(timestamp) as started, COUNT(*) as msg_count
           FROM chat_history WHERE user_id = ? GROUP BY session_id ORDER BY started DESC""",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_chat_logs():
    """For admin panel: every conversation across all users."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT ch.*, u.username FROM chat_history ch
        JOIN users u ON ch.user_id = u.id
        ORDER BY ch.timestamp DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- FEEDBACK ----------

def save_feedback(chat_id, user_id, rating):
    conn = get_connection()
    conn.execute(
        "INSERT INTO feedback (chat_id, user_id, rating, timestamp) VALUES (?, ?, ?, ?)",
        (chat_id, user_id, rating, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def get_feedback_stats():
    conn = get_connection()
    rows = conn.execute("""
        SELECT rating, COUNT(*) as count FROM feedback GROUP BY rating
    """).fetchall()
    conn.close()
    return {r["rating"]: r["count"] for r in rows}


def get_all_feedback():
    conn = get_connection()
    rows = conn.execute("""
        SELECT f.*, ch.message as bot_message, u.username FROM feedback f
        JOIN chat_history ch ON f.chat_id = ch.id
        JOIN users u ON f.user_id = u.id
        ORDER BY f.timestamp DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- KNOWLEDGE BASE ----------

def add_kb_entry(title, content, source="manual"):
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    cur = conn.execute(
        "INSERT INTO kb_entries (title, content, source, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (title, content, source, now, now)
    )
    conn.commit()
    entry_id = cur.lastrowid
    conn.close()
    return entry_id


def update_kb_entry(entry_id, title, content):
    conn = get_connection()
    conn.execute(
        "UPDATE kb_entries SET title = ?, content = ?, updated_at = ? WHERE id = ?",
        (title, content, datetime.utcnow().isoformat(), entry_id)
    )
    conn.commit()
    conn.close()


def delete_kb_entry(entry_id):
    conn = get_connection()
    conn.execute("DELETE FROM kb_entries WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()


def get_all_kb_entries():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM kb_entries ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- FAQ ----------

def get_all_faqs():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM faqs ORDER BY id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_faq(question, answer):
    conn = get_connection()
    conn.execute("INSERT INTO faqs (question, answer) VALUES (?, ?)", (question, answer))
    conn.commit()
    conn.close()


def delete_faq(faq_id):
    conn = get_connection()
    conn.execute("DELETE FROM faqs WHERE id = ?", (faq_id,))
    conn.commit()
    conn.close()
