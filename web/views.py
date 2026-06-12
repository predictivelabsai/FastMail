"""Center-pane renderers for FastMail."""
from __future__ import annotations

from datetime import datetime

from fasthtml.common import (
    Div, H1, H3, P, Span, A, Form, Input, Textarea, Button, Label, NotStr, Strong,
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

def _label_chip(l, removable_for=None):
    bits = [Span(l["name"])]
    if removable_for is not None:
        bits.append(Span("✕", cls="lbl-x", title="Remove label",
                         **{"hx-post": f"/message/{removable_for}/label/{l['id']}/remove",
                            "hx-target": "#msg-labels", "hx-swap": "outerHTML"}))
    return Span(*bits, cls=f"lbl lbl-{l['color']}")


def _mlist_rows(msgs, folder):
    lmap = db.labels_map([m["id"] for m in msgs])
    rows = []
    for m in msgs:
        peer = m["from_name"] if folder in ("Inbox", "Spam", "Trash", "Archive", "Starred") else f"To: {m['to_name']}"
        chips = [_label_chip(l) for l in lmap.get(m["id"], [])]
        rows.append(Div(
            Span(NotStr("&#9733;") if m["is_starred"] else NotStr("&#9734;"),
                 cls=f"star {'on' if m['is_starred'] else ''}",
                 **{"hx-post": f"/star/{m['id']}", "hx-swap": "outerHTML", "hx-trigger": "click consume"}),
            Span(peer, cls="who"),
            Div(Span(m["subject"] or "(no subject)", cls="subj-t"), " ",
                *( [Span(*chips, cls="row-labels")] if chips else [] ),
                Span("— " + (m["snippet"] or ""), cls="snip"), cls="subj"),
            Span(NotStr("&#128206;") if m["has_attach"] else "", cls="attach"),
            Span(_when(m["sent_at"]), cls="when"),
            cls=f"mrow {'unread' if not m['is_read'] else ''}",
            onclick=f"openMsg({m['id']})"))
    return rows


_SEARCH_HINT = ("Operators: from: to: subject: label: in: is:unread is:starred has:attachment")


def folder_view(folder: str, q: str = ""):
    msgs = db.messages_in(folder, q)
    head = Div(Div(H1(folder), P(f"{len(msgs)} messages", cls="sub")), cls="list-head")
    search = Div(Form(Input(type="search", name="q", value=q,
                            placeholder=f"Search {folder} — try from:acme is:unread", autocomplete="off"),
                      method="get", action=f"/folder/{folder}"),
                 Div(_SEARCH_HINT, cls="search-hint"), cls="searchbar")
    if not msgs:
        return head, search, Div(P(f"No messages in {folder}." + (" Try a different search." if q else "")), cls="empty")
    return head, search, Div(*_mlist_rows(msgs, folder), cls="mlist")


def label_view(lid: int):
    l = db.label(lid)
    if not l:
        return Div(P("Label not found."), cls="empty")
    msgs = db.messages_by_label(lid)
    head = Div(Div(H1(NotStr(f"Label: <span class='lbl lbl-{l['color']}'>{l['name']}</span>")),
                   P(f"{len(msgs)} messages", cls="sub")), cls="list-head")
    if not msgs:
        return head, Div(P("No messages with this label."), cls="empty")
    return head, Div(*_mlist_rows(msgs, "Inbox"), cls="mlist")


def star_cell(mid: int):
    m = db.message(mid)
    return Span(NotStr("&#9733;") if m["is_starred"] else NotStr("&#9734;"),
                cls=f"star {'on' if m['is_starred'] else ''}",
                **{"hx-post": f"/star/{mid}", "hx-swap": "outerHTML", "hx-trigger": "click consume"})


# ---------- reading view ----------------------------------------------------

def message_main(mid: int):
    """Reading body (thread + reply + AI panel), returned standalone for HTMX swaps."""
    m = db.message(mid)
    if not m:
        return Div(P("Message not found."), cls="empty")
    msgs = db.thread(m["thread_id"]) if m["thread_id"] else [m]
    last = msgs[-1] if msgs else m
    emails = []
    for e in msgs:
        emails.append(Div(
            Div(Div(Span(_initials(e["from_name"]), cls="avatar"),
                    Span(e["from_name"] or e["from_email"], cls="from"),
                    Span(f"  <{e['from_email']}>", cls="addr")),
                Span(e["sent_at"][:16], cls="when"), cls="email-head"),
            Div(e["body"] or "", cls="email-body"), cls="email"))
    reply_box = Form(
        Textarea("", name="body", placeholder=f"Reply to {last['from_name']}…", required=True),
        Div(Button("↩ Send reply", cls="btn primary", type="submit"),
            Button("✍️ AI draft", cls="btn", type="button",
                   **{"hx-post": f"/ai/draft/{last['id']}", "hx-target": "#ai-panel", "hx-swap": "innerHTML"}),
            style="margin-top:8px;display:flex;gap:8px;"),
        **{"hx-post": f"/reply/{last['id']}", "hx-target": "#msg-main", "hx-swap": "innerHTML"},
        cls="reply-box")
    return Div(Div(id="ai-panel", style="margin-bottom:12px;"), *emails, reply_box)


def message_view(mid: int):
    m = db.message(mid)
    if not m:
        return Div(P("Message not found."), cls="empty")
    db.mark_read(mid)
    folder = m["folder"]
    actions = Div(
        A("← Back", href=f"/folder/{folder}", cls="btn"),
        Button("✨ Summarise", cls="btn",
               **{"hx-post": f"/ai/summarise/{m['thread_id'] or 0}/{mid}", "hx-target": "#ai-panel", "hx-swap": "innerHTML"}),
        Button("📥 Archive", cls="btn", **{"hx-post": f"/msg/{mid}/move", "hx-vals": '{"folder":"Archive"}'}),
        Button("🗑 Trash", cls="btn", **{"hx-post": f"/msg/{mid}/move", "hx-vals": '{"folder":"Trash"}'}),
        Button("Mark unread", cls="btn", **{"hx-post": f"/msg/{mid}/unread"}),
        cls="read-actions")
    return Div(
        Div(Div(H1(m["subject"] or "(no subject)"), cls="read-head"),
            actions,
            msg_labels(mid),
            Div(message_main(mid), id="msg-main", style="margin-top:12px;"),
            cls="reading"))


def msg_labels(mid: int):
    """Labels on a message + an 'add label' picker. Swapped on change."""
    on = db.labels_for(mid)
    on_ids = {l["id"] for l in on}
    available = [l for l in db.labels() if l["id"] not in on_ids]
    chips = [_label_chip(l, removable_for=mid) for l in on]
    picker = None
    if available:
        opts = "".join(f'<option value="{l["id"]}">{l["name"]}</option>' for l in available)
        picker = NotStr(
            f'<select class="lbl-add" '
            f'hx-post="/message/{mid}/label/add" hx-target="#msg-labels" hx-swap="outerHTML" '
            f'hx-trigger="change" name="label_id">'
            f'<option value="">+ Add label…</option>{opts}</select>')
    return Div(Span("🏷", style="opacity:.6;"), *chips,
               (picker if picker is not None else Span("All labels applied", cls="sub")),
               A("Manage", href="/labels", cls="lbl-manage"),
               id="msg-labels", cls="msg-labels")


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


# ---------- labels management ----------------------------------------------

def labels_manage():
    ls = db.labels()
    rows_ = [Div(
        _label_chip(l),
        Span(f"{l['n']} messages", style="color:var(--text-mute);font-size:12px;"),
        A("View", href=f"/label/{l['id']}", cls="btn sm"),
        Form(Button("🗑", cls="btn sm", type="submit"),
             method="post", action=f"/labels/{l['id']}/delete", style="display:inline;"),
        cls="label-row") for l in ls]
    color_opts = "".join(f'<option value="{c}">{c}</option>' for c in db.LABEL_COLORS)
    add = Form(
        Input(name="name", placeholder="Label name", required=True,
              style="padding:8px 10px;border:1px solid var(--border);border-radius:8px;"),
        NotStr(f'<select name="color" style="padding:8px 10px;border:1px solid var(--border);border-radius:8px;">{color_opts}</select>'),
        Button("Create label", cls="btn primary", type="submit"),
        method="post", action="/labels/new",
        style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;")
    return (Div(H1("Labels"), P(f"{len(ls)} labels", cls="sub"), cls="list-head"),
            Div(Div(H3("New label"), cls="card-header"), add, cls="card"),
            Div(Div(H3("Your labels"), cls="card-header"),
                Div(*rows_ or [P("No labels yet.", cls="sub")]), cls="card"))


# ---------- calendar --------------------------------------------------------

_MONTHS = ["", "January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"]
_DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def calendar_view(year: int, month: int, sel_date: str = ""):
    import calendar as _cal
    from datetime import date as _date
    today = _date(2026, 6, 11)
    cal = _cal.Calendar(firstweekday=0)  # Monday
    weeks = cal.monthdatescalendar(year, month)
    # events for the visible range
    first = weeks[0][0].isoformat()
    last = (weeks[-1][-1]).isoformat()
    evs = db.events_between(first + " 00:00", last + " 23:59")
    by_day: dict = {}
    for e in evs:
        by_day.setdefault(e["start_at"][:10], []).append(e)

    prev_m = (month - 1) or 12
    prev_y = year - 1 if month == 1 else year
    next_m = (month % 12) + 1
    next_y = year + 1 if month == 12 else year

    dow_head = Div(*[Div(d, cls="cal-dow") for d in _DOW], cls="cal-row cal-head")
    week_rows = []
    for wk in weeks:
        cells = []
        for d in wk:
            iso = d.isoformat()
            day_evs = by_day.get(iso, [])
            chips = [A(f"{e['start_at'][11:16]} {e['title']}"[:22],
                       href=f"/calendar?sel={iso}", cls=f"cal-ev lbl-{e['color']}",
                       title=e["title"]) for e in day_evs[:3]]
            more = [Span(f"+{len(day_evs)-3} more", cls="cal-more")] if len(day_evs) > 3 else []
            cls = "cal-cell"
            if d.month != month:
                cls += " other"
            if d == today:
                cls += " today"
            cells.append(A(Div(str(d.day), cls="cal-num"), *chips, *more,
                           href=f"/calendar?sel={iso}", cls=cls))
        week_rows.append(Div(*cells, cls="cal-row"))

    # side panel: events on the selected day (or upcoming)
    if sel_date:
        day_evs = sorted(by_day.get(sel_date, []), key=lambda e: e["start_at"])
        panel_title = f"Events on {sel_date}"
        panel_list = day_evs
    else:
        panel_list = db.upcoming_events(today.isoformat() + " 00:00")
        panel_title = "Upcoming"
    panel_items = [Div(
        Span(NotStr("&#9679;"), cls=f"dot-{e['color']}"),
        Div(Strong(e["title"]),
            Div(f"{e['start_at'][:16]}" + (f" → {e['end_at'][11:16]}" if e["end_at"] else ""),
                cls="sub"),
            Div(e["location"] or "", style="color:var(--text-mute);font-size:12px;") if e["location"] else None),
        Form(Button("🗑", cls="btn sm", type="submit"), method="post",
             action=f"/calendar/{e['id']}/delete", style="display:inline;margin-left:auto;"),
        cls="ev-item") for e in panel_list] or [P("Nothing scheduled.", cls="sub")]

    new_form = Form(
        Input(name="title", placeholder="Event title", required=True,
              style="width:100%;padding:8px;border:1px solid var(--border);border-radius:8px;margin-bottom:6px;"),
        Input(name="start_at", type="datetime-local", required=True, value=(sel_date + "T09:00") if sel_date else "",
              style="width:100%;padding:8px;border:1px solid var(--border);border-radius:8px;margin-bottom:6px;"),
        Input(name="location", placeholder="Location (optional)",
              style="width:100%;padding:8px;border:1px solid var(--border);border-radius:8px;margin-bottom:6px;"),
        Button("Add event", cls="btn primary", type="submit"),
        method="post", action="/calendar/new")

    return (
        Div(Div(H1(f"{_MONTHS[month]} {year}"),
                P("Calendar — synthetic demo events.", cls="sub")),
            Div(A("‹ Prev", href=f"/calendar?year={prev_y}&month={prev_m}", cls="btn"),
                A("Today", href="/calendar", cls="btn"),
                A("Next ›", href=f"/calendar?year={next_y}&month={next_m}", cls="btn"),
                style="display:flex;gap:6px;"),
            cls="list-head", style="display:flex;justify-content:space-between;align-items:center;"),
        Div(
            Div(dow_head, *week_rows, cls="cal-grid"),
            Div(Div(Div(H3(panel_title), cls="card-header"), *panel_items, cls="card"),
                Div(Div(H3("New event"), cls="card-header"), new_form, cls="card")),
            cls="cal-layout"))
