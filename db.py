"""FastMail data layer — SQLite webmail.

A webmail client over a synthetic mailbox. Frappe Mail is really a mail *server*
(SMTP/IMAP, queues, DNS); FastMail demonstrates the **client** half: folders,
messages, threads, an address book, and AI summarise/draft.
"""
from __future__ import annotations

import os
import re
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
CREATE TABLE IF NOT EXISTS labels (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    color         TEXT NOT NULL DEFAULT 'gray'
);
CREATE TABLE IF NOT EXISTS message_labels (
    message_id    INTEGER REFERENCES messages(id),
    label_id      INTEGER REFERENCES labels(id),
    PRIMARY KEY (message_id, label_id)
);
CREATE TABLE IF NOT EXISTS events (
    id            INTEGER PRIMARY KEY,
    title         TEXT NOT NULL,
    start_at      TEXT NOT NULL,        -- 'YYYY-MM-DD HH:MM'
    end_at        TEXT,
    location      TEXT,
    notes         TEXT,
    color         TEXT NOT NULL DEFAULT 'blue'
);
CREATE INDEX IF NOT EXISTS idx_msg_folder ON messages(folder);
CREATE INDEX IF NOT EXISTS idx_msg_thread ON messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_mlabel_msg ON message_labels(message_id);
CREATE INDEX IF NOT EXISTS idx_events_start ON events(start_at);
"""

LABEL_COLORS = ["gray", "blue", "green", "amber", "red", "purple", "teal", "pink"]


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


# --- search operators -------------------------------------------------------

_OP_RE = re.compile(r'(\w+):("[^"]*"|\S+)')
SEARCH_OPERATORS = ["from:", "to:", "subject:", "is:unread", "is:read",
                    "is:starred", "has:attachment", "label:", "in:"]


def parse_search(q: str):
    """Parse a Gmail-style query into SQL. Returns (clauses, params,
    scoped_folder, label_filter)."""
    clauses, params = [], []
    scoped_folder = None
    label_filter = None
    free = q or ""
    for m in _OP_RE.finditer(q or ""):
        key, val = m.group(1).lower(), m.group(2).strip('"')
        free = free.replace(m.group(0), " ")
        if key == "from":
            clauses.append("(from_name LIKE ? OR from_email LIKE ?)"); params += [f"%{val}%"] * 2
        elif key == "to":
            clauses.append("(to_name LIKE ? OR to_email LIKE ?)"); params += [f"%{val}%"] * 2
        elif key == "subject":
            clauses.append("subject LIKE ?"); params.append(f"%{val}%")
        elif key == "is":
            v = val.lower()
            if v == "unread":
                clauses.append("is_read=0")
            elif v == "read":
                clauses.append("is_read=1")
            elif v == "starred":
                clauses.append("is_starred=1")
        elif key == "has":
            if val.lower().startswith("attach"):
                clauses.append("has_attach=1")
        elif key == "in":
            scoped_folder = val.capitalize()
        elif key == "label":
            label_filter = val
    free = " ".join(free.split()).strip()
    if free:
        clauses.append("(subject LIKE ? OR from_name LIKE ? OR from_email LIKE ? OR body LIKE ?)")
        params += [f"%{free}%"] * 4
    return clauses, params, scoped_folder, label_filter


def messages_in(folder: str, q: str = "") -> list[dict]:
    clauses, params, scoped_folder, label_filter = parse_search(q) if q else ([], [], None, None)
    eff = scoped_folder or folder
    where, wp = [], []
    if eff == "Starred":
        where.append("is_starred=1 AND folder!='Trash'")
    else:
        where.append("folder=?"); wp.append(eff)
    if label_filter:
        where.append("id IN (SELECT ml.message_id FROM message_labels ml "
                     "JOIN labels l ON l.id=ml.label_id WHERE l.name LIKE ?)")
        wp.append(f"%{label_filter}%")
    where += clauses
    return rows(f"SELECT * FROM messages WHERE {' AND '.join(where)} ORDER BY sent_at DESC LIMIT 200",
                tuple(wp + params))


# --- labels -----------------------------------------------------------------

def labels() -> list[dict]:
    return rows("""SELECT l.*,
                     (SELECT COUNT(*) FROM message_labels ml JOIN messages m ON m.id=ml.message_id
                      WHERE ml.label_id=l.id AND m.folder!='Trash') n
                   FROM labels l ORDER BY l.name""")


def label(lid: int):
    return one("SELECT * FROM labels WHERE id=?", (lid,))


def create_label(name: str, color: str = "gray") -> int | None:
    name = (name or "").strip()
    if not name:
        return None
    if color not in LABEL_COLORS:
        color = "gray"
    with cursor() as conn:
        existing = conn.execute("SELECT id FROM labels WHERE name=?", (name,)).fetchone()
        if existing:
            return existing[0]
        conn.execute("INSERT INTO labels(name,color) VALUES (?,?)", (name, color))
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def delete_label(lid: int):
    with cursor() as conn:
        conn.execute("DELETE FROM message_labels WHERE label_id=?", (lid,))
        conn.execute("DELETE FROM labels WHERE id=?", (lid,))


def labels_for(mid: int) -> list[dict]:
    return rows("""SELECT l.* FROM labels l JOIN message_labels ml ON ml.label_id=l.id
                   WHERE ml.message_id=? ORDER BY l.name""", (mid,))


def labels_map(mids: list[int]) -> dict:
    """Batch: {message_id: [labels]} for a list view."""
    if not mids:
        return {}
    qmarks = ",".join("?" * len(mids))
    rs = rows(f"""SELECT ml.message_id mid, l.id, l.name, l.color
                  FROM message_labels ml JOIN labels l ON l.id=ml.label_id
                  WHERE ml.message_id IN ({qmarks}) ORDER BY l.name""", tuple(mids))
    out: dict = {}
    for r in rs:
        out.setdefault(r["mid"], []).append(r)
    return out


def add_label(mid: int, label_id: int):
    with cursor() as conn:
        conn.execute("INSERT OR IGNORE INTO message_labels(message_id,label_id) VALUES (?,?)", (mid, label_id))


def remove_label(mid: int, label_id: int):
    with cursor() as conn:
        conn.execute("DELETE FROM message_labels WHERE message_id=? AND label_id=?", (mid, label_id))


def messages_by_label(label_id: int) -> list[dict]:
    return rows("""SELECT m.* FROM messages m JOIN message_labels ml ON ml.message_id=m.id
                   WHERE ml.label_id=? AND m.folder!='Trash' ORDER BY m.sent_at DESC LIMIT 200""",
                (label_id,))


# --- calendar / events ------------------------------------------------------

def events_between(start_date: str, end_date: str) -> list[dict]:
    return rows("SELECT * FROM events WHERE start_at >= ? AND start_at < ? ORDER BY start_at",
                (start_date, end_date))


def event(eid: int):
    return one("SELECT * FROM events WHERE id=?", (eid,))


def upcoming_events(from_dt: str, limit: int = 8) -> list[dict]:
    return rows("SELECT * FROM events WHERE start_at >= ? ORDER BY start_at LIMIT ?", (from_dt, limit))


def create_event(title: str, start_at: str, end_at: str = "", location: str = "",
                 notes: str = "", color: str = "blue") -> int | None:
    title, start_at = (title or "").strip(), (start_at or "").strip()
    if not title or not start_at:
        return None
    if color not in LABEL_COLORS:
        color = "blue"
    with cursor() as conn:
        conn.execute("INSERT INTO events(title,start_at,end_at,location,notes,color) VALUES (?,?,?,?,?,?)",
                     (title, start_at, end_at or None, location or None, notes or None, color))
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def delete_event(eid: int):
    with cursor() as conn:
        conn.execute("DELETE FROM events WHERE id=?", (eid,))


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
