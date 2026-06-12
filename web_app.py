"""FastMail — an open-source webmail client built with FastHTML.

A server-side, HTMX-driven take on the client half of Frappe Mail: folders,
message list, threaded reading pane, compose, an address book, and AI
summarise-thread / draft-reply — all over a synthetic mailbox.

Run:
    python web_app.py            # http://localhost:5009

Login: admin@fastmail.example / FastMail2026$  (override via .env)
"""
from __future__ import annotations

import os
import json
import secrets
import uuid
import logging

from dotenv import load_dotenv
load_dotenv()

from fasthtml.common import (
    fast_app, serve, Div, H1, P, A, Form, Input, Button, NotStr,
    RedirectResponse, Script, Style, Link, Title,
)
from starlette.responses import StreamingResponse, Response

import db
from web.layout import page, LAYOUT_CSS
from web import views, ai

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("fastmail")

VALID_EMAIL = os.getenv("FASTMAIL_ADMIN_EMAIL", "admin@fastmail.example")
VALID_PASSWORD = os.getenv("FASTMAIL_ADMIN_PASSWORD", "FastMail2026$")
ENV_LABEL = os.getenv("FASTMAIL_ENV_LABEL", "FastMail")
SECRET = os.getenv("FASTMAIL_SECRET", secrets.token_hex(32))
PORT = int(os.getenv("FASTMAIL_PORT", "5009"))

app, rt = fast_app(live=False, pico=False, secret_key=SECRET, hdrs=[Style(LAYOUT_CSS)])


def _user(session):
    return session.get("user")


def _thread(session):
    if "thread" not in session:
        session["thread"] = uuid.uuid4().hex
    return session["thread"]


def _guard(session, active, builder):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    content = builder() if callable(builder) else builder
    if not isinstance(content, tuple):
        content = (content,)
    return page(active, ENV_LABEL, _user(session), _thread(session), db.folder_counts(), *content)


def _login_card(error="", email=""):
    return Title("FastMail — Sign in"), Style(LAYOUT_CSS), Div(
        Form(H1("FastMail"), P("Sign in to your inbox"),
             Input(name="email", type="email", placeholder="Email", value=email, required=True),
             Input(name="password", type="password", placeholder="Password", required=True),
             P(error, cls="error") if error else None,
             Button("Sign in", cls="btn primary", type="submit"),
             P(NotStr("Demo: <code>admin@fastmail.example</code> / <code>FastMail2026$</code>"), cls="hint"),
             method="post", action="/login", cls="login-card"), cls="login-wrap")


@rt("/login")
def get(session):
    if _user(session):
        return RedirectResponse("/", status_code=303)
    return _login_card()


@rt("/login")
def post(session, email: str = "", password: str = ""):
    if email.strip().lower() == VALID_EMAIL.lower() and password == VALID_PASSWORD:
        session["user"] = email.strip().lower()
        return RedirectResponse("/", status_code=303)
    return _login_card("Invalid email or password.", email)


@rt("/logout")
def get(session):
    session.pop("user", None)
    return RedirectResponse("/login", status_code=303)


@rt("/")
def get(session):
    return RedirectResponse("/folder/Inbox", status_code=303) if _user(session) else RedirectResponse("/login", status_code=303)


@rt("/folder/{folder}")
def get(session, folder: str, q: str = ""):
    return _guard(session, folder, lambda: views.folder_view(folder, q))


@rt("/message/{mid}")
def get(session, mid: int):
    m = db.message(mid)
    active = m["folder"] if m else "Inbox"
    return _guard(session, active, lambda: views.message_view(mid))


@rt("/star/{mid}")
def post(session, mid: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    db.toggle_star(mid)
    return views.star_cell(mid)


@rt("/reply/{mid}")
def post(session, mid: int, body: str = ""):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    db.send_reply(mid, body)
    return views.message_main(mid)


@rt("/msg/{mid}/move")
def post(session, mid: int, folder: str = "Archive"):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    src = db.message(mid)
    db.move_to(mid, folder if folder in db.FOLDERS else "Archive")
    return Response(headers={"HX-Redirect": f"/folder/{src['folder'] if src else 'Inbox'}"})


@rt("/msg/{mid}/unread")
def post(session, mid: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    src = db.message(mid)
    db.set_read(mid, False)
    return Response(headers={"HX-Redirect": f"/folder/{src['folder'] if src else 'Inbox'}"})


@rt("/compose")
def get(session, reply: int | None = None):
    return _guard(session, "compose", lambda: views.compose_view(reply))


@rt("/send")
def post(session, to: str = "", subject: str = "", body: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    to_name = to.split("<")[0].strip() or to
    to_email = to.split("<")[-1].rstrip(">").strip() if "<" in to else to
    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO messages(thread_id,folder,from_name,from_email,to_name,to_email,subject,body,snippet,sent_at,is_read)
               VALUES (NULL,'Sent',?,?,?,?,?,?,?,datetime('now'),1)""",
            (db.ACCOUNT_NAME, db.ACCOUNT_EMAIL, to_name, to_email, subject, body, (body or "")[:110]))
    return _guard(session, "compose", lambda: views.compose_view(sent=True))


@rt("/contacts")
def get(session):
    return _guard(session, "contacts", views.contacts_view)


# --- labels -----------------------------------------------------------------

@rt("/labels")
def get(session):
    return _guard(session, "labels", views.labels_manage)


@rt("/labels/new")
def post(session, name: str = "", color: str = "gray"):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    db.create_label(name, color)
    return RedirectResponse("/labels", status_code=303)


@rt("/labels/{lid}/delete")
def post(session, lid: int):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    db.delete_label(lid)
    return RedirectResponse("/labels", status_code=303)


@rt("/label/{lid}")
def get(session, lid: int):
    return _guard(session, f"label-{lid}", lambda: views.label_view(lid))


@rt("/message/{mid}/label/add")
def post(session, mid: int, label_id: str = ""):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    if label_id:
        db.add_label(mid, int(label_id))
    return views.msg_labels(mid)


@rt("/message/{mid}/label/{lid}/remove")
def post(session, mid: int, lid: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    db.remove_label(mid, lid)
    return views.msg_labels(mid)


# --- calendar ---------------------------------------------------------------

@rt("/calendar")
def get(session, year: int = 2026, month: int = 6, sel: str = ""):
    if month < 1 or month > 12:
        year, month = 2026, 6
    return _guard(session, "calendar", lambda: views.calendar_view(year, month, sel))


@rt("/calendar/new")
def post(session, title: str = "", start_at: str = "", location: str = "", notes: str = ""):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    start = (start_at or "").replace("T", " ")[:16]
    db.create_event(title, start, location=location, notes=notes)
    day = start[:10]
    return RedirectResponse(f"/calendar?sel={day}" if day else "/calendar", status_code=303)


@rt("/calendar/{eid}/delete")
def post(session, eid: int):
    if not _user(session):
        return RedirectResponse("/login", status_code=303)
    ev = db.event(eid)
    db.delete_event(eid)
    day = ev["start_at"][:10] if ev else ""
    return RedirectResponse(f"/calendar?sel={day}" if day else "/calendar", status_code=303)


@rt("/ai/summarise/{tid}/{mid}")
def post(session, tid: int, mid: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    try:
        return views.ai_panel(ai.summarise_thread(tid, mid), "Thread summary")
    except Exception as e:  # noqa: BLE001
        return views.ai_panel(str(e), "AI unavailable")


@rt("/ai/draft/{mid}")
def post(session, mid: int):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    try:
        return views.ai_panel(ai.draft_reply(mid), "Draft reply")
    except Exception as e:  # noqa: BLE001
        return views.ai_panel(str(e), "AI unavailable")


@rt("/ai")
def get(session):
    body = (Div(H1("AI Assistant"), P("Chat lives in the right rail.", cls="sub"), cls="list-head"),
            Div(NotStr(
                "<div style='padding:20px 24px;'><div class='email'><div class='email-body'>"
                "<h3>What you can ask</h3><ul style='line-height:1.8;'>"
                "<li>“What needs my reply today?”</li><li>“Summarise my unread mail.”</li>"
                "<li>“Find the renewal thread.”</li></ul>"
                "<p>Slash-commands (no API key): <code>/unread</code> <code>/find &lt;text&gt;</code> <code>/starred</code></p>"
                "<p>Open any message to <b>summarise the thread</b> or <b>draft a reply</b> with AI.</p>"
                "</div></div></div>")))
    return _guard(session, "ai", body)


@rt("/guide")
def get(session):
    body = (Div(H1("User Guide"), cls="list-head"), Div(NotStr("""
<div style='padding:20px 24px;max-width:820px;'>
<div class='email'><div class='email-body'><h3>Folders</h3>Inbox, Starred, Sent, Drafts, Archive, Spam, Trash —
with unread badges. Click a message to read the whole thread.</div></div>
<div class='email'><div class='email-body'><h3>Reading</h3>Star/unstar inline, reply, or use AI to
<b>summarise the thread</b> or <b>draft a reply</b> you can edit before sending.</div></div>
<div class='email'><div class='email-body'><h3>Compose & Contacts</h3>Write new mail (saved to Sent) and
browse your address book.</div></div>
<div class='email'><div class='email-body'><h3>AI Assistant</h3>The right rail chats over a live snapshot of
your mailbox. Set <code>MODEL_PROVIDER</code> + a key in <code>.env</code> for free-form chat & summarise/draft;
slash-commands always work.</div></div></div>""")))
    return _guard(session, "guide", body)


@rt("/chat/new")
def get(session):
    session["thread"] = uuid.uuid4().hex
    return P("Ask about your mailbox — or use /unread /find /help.", cls="chat-empty-hint")


@rt("/chat/stream")
async def post(session, message: str = "", thread_id: str = ""):
    if not _user(session):
        return Response("Unauthorized", status_code=401)
    message = (message or "").strip()
    if not message:
        return Response("No message", status_code=400)
    tid = thread_id or _thread(session)

    async def gen():
        with db.cursor() as conn:
            conn.execute("INSERT INTO chat_messages(thread_id,role,content,created) VALUES(?,?,?,datetime('now'))",
                         (tid, "user", message))
        full = []
        async for chunk in ai.stream_chat(message):
            if chunk.startswith("data: "):
                try:
                    tok = json.loads(chunk[6:]).get("token")
                    if tok:
                        full.append(tok)
                except Exception:
                    pass
            yield chunk
        with db.cursor() as conn:
            conn.execute("INSERT INTO chat_messages(thread_id,role,content,created) VALUES(?,?,?,datetime('now'))",
                         (tid, "assistant", "".join(full)))

    return StreamingResponse(gen(), media_type="text/event-stream")


def _ensure_db():
    if not db.db_exists():
        logger.info("No database found — seeding synthetic mailbox…")
        import seed
        seed.build()
    else:
        db.init_schema()  # idempotent; creates labels / message_labels / events


_ensure_db()

if __name__ == "__main__":
    logger.info("FastMail on http://localhost:%s  (login %s)", PORT, VALID_EMAIL)
    serve(port=PORT, reload=os.getenv("FASTMAIL_RELOAD", "0") == "1")
