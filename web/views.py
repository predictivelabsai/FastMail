"""Center-pane renderers for FastMail."""
from __future__ import annotations

from datetime import datetime

from fasthtml.common import (
    Div, H1, H3, P, Span, A, Form, Input, Textarea, Button, Label, NotStr,
)

import db


def _when(ts: str) -> str:
    try:
        dt = datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return ts[:10]
    now = datetime(2026, 6, 11, 12, 0, 0)
    if dt.date() == now.date():
        return dt.strftime("%H:%M")
    if (now - dt).days < 7:
        return dt.strftime("%a")
    return dt.strftime("%d %b")


def _initials(name: str) -> str:
    parts = (name or "?").split()
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


# ---------- message list ----------------------------------------------------

def folder_view(folder: str, q: str = ""):
    msgs = db.messages_in(folder, q)
    rows = []
    for m in msgs:
        peer = m["from_name"] if folder in ("Inbox", "Spam", "Trash", "Archive", "Starred") else f"To: {m['to_name']}"
        rows.append(Div(
            Span(NotStr("&#9733;") if m["is_starred"] else NotStr("&#9734;"),
                 cls=f"star {'on' if m['is_starred'] else ''}",
                 **{"hx-post": f"/star/{m['id']}", "hx-swap": "outerHTML", "hx-trigger": "click consume"}),
            Span(peer, cls="who"),
            Div(Span(m["subject"] or "(no subject)", cls="subj-t"), " ",
                Span("— " + (m["snippet"] or ""), cls="snip"), cls="subj"),
            Span(_when(m["sent_at"]), cls="when"),
            cls=f"mrow {'unread' if not m['is_read'] else ''}",
            onclick=f"openMsg({m['id']})"))
    head = Div(Div(H1(folder), P(f"{len(msgs)} messages", cls="sub")), cls="list-head")
    search = Div(Form(Input(type="search", name="q", value=q,
                            placeholder=f"Search {folder}…", autocomplete="off"),
                      method="get", action=f"/folder/{folder}"), cls="searchbar")
    if not msgs:
        return head, search, Div(P(f"No messages in {folder}." + (" Try a different search." if q else "")), cls="empty")
    return head, search, Div(*rows, cls="mlist")


def star_cell(mid: int):
    m = db.message(mid)
    return Span(NotStr("&#9733;") if m["is_starred"] else NotStr("&#9734;"),
                cls=f"star {'on' if m['is_starred'] else ''}",
                **{"hx-post": f"/star/{mid}", "hx-swap": "outerHTML", "hx-trigger": "click consume"})


# ---------- reading view ----------------------------------------------------

def message_view(mid: int):
    m = db.message(mid)
    if not m:
        return Div(P("Message not found."), cls="empty")
    db.mark_read(mid)
    msgs = db.thread(m["thread_id"]) if m["thread_id"] else [m]
    emails = []
    for e in msgs:
        emails.append(Div(
            Div(Div(Span(_initials(e["from_name"]), cls="avatar"),
                    Span(e["from_name"] or e["from_email"], cls="from"),
                    Span(f"  <{e['from_email']}>", cls="addr")),
                Span(e["sent_at"][:16], cls="when"), cls="email-head"),
            Div(e["body"] or "", cls="email-body"), cls="email"))
    back = A("← Back", href=f"/folder/{m['folder']}", cls="btn")
    actions = Div(
        Button("✨ Summarise thread", cls="btn primary",
               **{"hx-post": f"/ai/summarise/{m['thread_id'] or 0}/{mid}", "hx-target": "#ai-panel", "hx-swap": "innerHTML"}),
        Button("✍️ Draft reply", cls="btn",
               **{"hx-post": f"/ai/draft/{mid}", "hx-target": "#ai-panel", "hx-swap": "innerHTML"}),
        A("↩ Reply", href=f"/compose?reply={mid}", cls="btn"),
        cls="read-actions")
    return Div(
        Div(Div(H1(m["subject"] or "(no subject)"), back, cls="read-head"),
            actions,
            Div(id="ai-panel", style="margin-top:12px;"),
            *emails,
            cls="reading"))


def ai_panel(text: str, kind: str = "Summary"):
    return Div(Div(Span(f"✨ {kind}", style="font-weight:700;"), style="margin-bottom:4px;"),
               NotStr(text), cls="ai-panel")


# ---------- compose ---------------------------------------------------------

def compose_view(reply_to: int | None = None, sent: bool = False):
    to_v, subj_v, body_v = "", "", ""
    if reply_to:
        m = db.message(reply_to)
        if m:
            to_v = f"{m['from_name']} <{m['from_email']}>"
            subj_v = m["subject"] if (m["subject"] or "").startswith("Re:") else f"Re: {m['subject']}"
            body_v = "\n\n\n— On " + m["sent_at"][:16] + ", " + (m["from_name"] or "") + " wrote:\n> " + \
                     (m["body"] or "").replace("\n", "\n> ")
    notice = Div("✓ Message sent — saved to Sent.", cls="notice") if sent else None
    return Div(
        Div(H1("New message"), cls="list-head"),
        notice,
        Div(Form(
            Label("To"), Input(name="to", value=to_v, placeholder="name@example.com"),
            Label("Subject"), Input(name="subject", value=subj_v, placeholder="Subject"),
            Label("Message"), Textarea(body_v, name="body", placeholder="Write your message…"),
            Div(Button("Send", cls="btn primary", type="submit"),
                A("Discard", href="/folder/Inbox", cls="btn"),
                style="margin-top:14px;display:flex;gap:8px;"),
            method="post", action="/send", cls="card"),
            cls="compose"))


# ---------- contacts --------------------------------------------------------

def contacts_view():
    cs = db.rows("SELECT * FROM contacts ORDER BY name")
    cards = [Div(Span(_initials(c["name"]), cls="avatar"),
                 Div(Div(c["name"], cls="nm"), Div(c["email"], cls="em"),
                     Div(c["company"] or "", style="color:var(--text-mute);font-size:12px;")))
             for c in cs]
    return Div(H1("Contacts"), P(f"{len(cs)} contacts", cls="sub"), cls="list-head"), \
        Div(*[Div(c, cls="contact-card") for c in cards], cls="contacts-grid")
