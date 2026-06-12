"""FastMail data layer — SQLite webmail.

A webmail client over a synthetic mailbox. Frappe Mail is really a mail *server*
(SMTP/IMAP, queues, DNS); FastMail demonstrates the **client** half: folders,
messages, threads, an address book, and AI summarise/draft.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = os.getenv("FASTMAIL_DB") or str(Path(__file__).parent / "fastmail.sqlite")

# Folders shown in the sidebar (Starred is a virtual filter, not a folder).
FOLDERS = ["Inbox", "Sent", "Drafts", "Archive", "Spam", "Trash"]
ACCOUNT_NAME = "Avery Quinn"
ACCOUNT_EMAIL = "avery@fastmail.example"


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


@contextmanager
def cursor():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def db_exists() -> bool:
    p = Path(DB_PATH)
    return p.exists() and p.stat().st_size > 0


def rows(sql, params=()):
    with cursor() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def one(sql, params=()):
    with cursor() as conn:
        r = conn.execute(sql, params).fetchone()
        return dict(r) if r else None


def scalar(sql, params=()):
    with cursor() as conn:
        r = conn.execute(sql, params).fetchone()
        return r[0] if r else None


SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY,
    thread_id     INTEGER,
    folder        TEXT NOT NULL DEFAULT 'Inbox',
    from_name     TEXT,
    from_email    TEXT,
    to_name       TEXT,
    to_email      TEXT,
    subject       TEXT,
    body          TEXT,
    snippet       TEXT,
    sent_at       TEXT NOT NULL,
    is_read       INTEGER NOT NULL DEFAULT 0,
    is_starred    INTEGER NOT NULL DEFAULT 0,
    has_attach    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS contacts (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL,
    company       TEXT
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id            INTEGER PRIMARY KEY,
    thread_id     TEXT NOT NULL,
    role          TEXT NOT NULL,
    content       TEXT NOT NULL,
    created       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_msg_folder ON messages(folder);
CREATE INDEX IF NOT EXISTS idx_msg_thread ON messages(thread_id);
"""


def init_schema():
    with cursor() as conn:
        conn.executescript(SCHEMA)


# --- reads ------------------------------------------------------------------

def folder_counts() -> dict:
    out = {}
    for f in FOLDERS:
        total = scalar("SELECT COUNT(*) FROM messages WHERE folder=?", (f,)) or 0
        unread = scalar("SELECT COUNT(*) FROM messages WHERE folder=? AND is_read=0", (f,)) or 0
        out[f] = {"total": total, "unread": unread}
    out["Starred"] = {
        "total": scalar("SELECT COUNT(*) FROM messages WHERE is_starred=1 AND folder!='Trash'") or 0,
        "unread": scalar("SELECT COUNT(*) FROM messages WHERE is_starred=1 AND is_read=0 AND folder!='Trash'") or 0,
    }
    return out


def messages_in(folder: str, q: str = "") -> list[dict]:
    if folder == "Starred":
        where, params = "is_starred=1 AND folder!='Trash'", []
    else:
        where, params = "folder=?", [folder]
    if q:
        where += " AND (subject LIKE ? OR from_name LIKE ? OR from_email LIKE ? OR body LIKE ?)"
        params += [f"%{q}%"] * 4
    return rows(f"SELECT * FROM messages WHERE {where} ORDER BY sent_at DESC LIMIT 200", tuple(params))


def message(mid: int) -> dict | None:
    return one("SELECT * FROM messages WHERE id=?", (mid,))


def thread(thread_id: int) -> list[dict]:
    return rows("SELECT * FROM messages WHERE thread_id=? ORDER BY sent_at", (thread_id,))


def mark_read(mid: int):
    with cursor() as conn:
        conn.execute("UPDATE messages SET is_read=1 WHERE id=?", (mid,))


def toggle_star(mid: int) -> int:
    with cursor() as conn:
        conn.execute("UPDATE messages SET is_starred = 1 - is_starred WHERE id=?", (mid,))
        return conn.execute("SELECT is_starred FROM messages WHERE id=?", (mid,)).fetchone()[0]


def move_to(mid: int, folder: str):
    with cursor() as conn:
        conn.execute("UPDATE messages SET folder=? WHERE id=?", (folder, mid))


def set_read(mid: int, read: bool):
    with cursor() as conn:
        conn.execute("UPDATE messages SET is_read=? WHERE id=?", (1 if read else 0, mid))


def send_reply(in_reply_to: int, body: str):
    """Reply within a thread: a message from ME, foldered Sent, sharing the thread."""
    orig = message(in_reply_to)
    if not orig or not body.strip():
        return None
    tid = orig["thread_id"]
    subj = orig["subject"] or ""
    if not subj.lower().startswith("re:"):
        subj = "Re: " + subj
    snippet = body.replace("\n", " ").strip()[:110]
    with cursor() as conn:
        conn.execute(
            """INSERT INTO messages(thread_id,folder,from_name,from_email,to_name,to_email,subject,body,snippet,sent_at,is_read)
               VALUES (?,'Sent',?,?,?,?,?,?,?,datetime('now'),1)""",
            (tid, ACCOUNT_NAME, ACCOUNT_EMAIL, orig["from_name"], orig["from_email"], subj, body.strip(), snippet))
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
