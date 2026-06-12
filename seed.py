"""Generate a synthetic FastMail mailbox (deterministic, no real PII)."""
from __future__ import annotations

import random
from datetime import datetime, timedelta

import db

RNG = random.Random(20260611)
NOW = datetime(2026, 6, 11, 12, 0, 0)
ME = (db.ACCOUNT_NAME, db.ACCOUNT_EMAIL)

PEOPLE = [
    ("Priya Nair", "priya@northwind.example", "Northwind Retail"),
    ("Tom Becker", "tom.becker@apexlog.example", "Apex Logistics"),
    ("Lena Sokolova", "lena@lumenhealth.example", "Lumen Health"),
    ("Marco Bianchi", "marco@heliosenergy.example", "Helios Energy"),
    ("Aisha Bello", "aisha@vertex.example", "Vertex Digital"),
    ("Kenji Watanabe", "kenji@cobaltfoods.example", "Cobalt Foods"),
    ("Sara Lindholm", "sara@bluewave.example", "Bluewave Media"),
    ("Diego Ramos", "diego@sterling.example", "Sterling Bank"),
    ("Nora Haddad", "nora@quantalabs.example", "Quanta Labs"),
    ("Felix Bauer", "felix@evergreen.example", "Evergreen Group"),
    ("Maya Petrov", "maya@meridian.example", "Meridian Travel"),
    ("Omar Khan", "omar@ironclad.example", "Ironclad Security"),
]

INBOX_THREADS = [
    ("Q3 partnership proposal", [
        ("them", "Hi Avery,\n\nFollowing our call, I've attached the draft Q3 partnership proposal. The headline is a 15% revenue share on referred accounts, with a 3-month pilot.\n\nWould love your thoughts before Friday.\n\nBest,\n{name}"),
        ("me", "Thanks {first} — this looks promising. Two questions: is the 15% on gross or net, and can we extend the pilot to 4 months to cover a full quarter?\n\nAvery"),
        ("them", "Good questions. It's on net, and yes — 4 months works. I'll revise and resend.\n\n{name}"),
    ]),
    ("Invoice #4821 overdue", [
        ("them", "Hello Avery,\n\nOur records show invoice #4821 (£12,400) is now 14 days overdue. Could you let me know when we can expect payment?\n\nKind regards,\n{name}"),
    ]),
    ("Re: Onboarding next steps", [
        ("them", "Hi Avery, great to have you on board! Next steps: 1) confirm your team size, 2) pick a kickoff date, 3) share your data export. Anything you need from us?\n\n{name}"),
        ("me", "Thanks {first}. Team is 8, kickoff the week of the 22nd works, export coming tomorrow.\n\nAvery"),
    ]),
    ("Security questionnaire", [
        ("them", "Avery — legal asked me to send over the standard security questionnaire before we proceed. It's 20 questions, mostly about data handling and SSO. No rush, but ideally back by month-end.\n\n{name}"),
    ]),
    ("Lunch on Thursday?", [
        ("them", "Hey Avery, in town Thursday — fancy lunch near your office around 12:30? Would be great to catch up properly.\n\n{name}"),
    ]),
    ("Renewal — 20% uplift concern", [
        ("them", "Hi Avery,\n\nWe received the renewal quote and the 20% uplift is hard to justify internally given flat usage. Is there room to discuss? We value the partnership and want to continue.\n\n{name}"),
        ("me", "Appreciate the candour, {first}. Let's find a number that works — can you do a 2-year term? That unlocks better pricing on our side.\n\nAvery"),
    ]),
    ("Webinar slides + recording", [
        ("them", "Thanks for joining yesterday's webinar! As promised, here are the slides and the recording link. Let me know if you'd like a tailored follow-up for your team.\n\n{name}"),
    ]),
    ("Bug: export skips rows", [
        ("them", "Avery, quick heads up — when I export to CSV, about 40 rows are missing each time. Reproduces on Chrome and Firefox. Happy to screen-share.\n\n{name}"),
    ]),
]

SPAM = [
    ("You've WON a £1,000 gift card!!!", "Claim your reward now — limited time only. Click here."),
    ("Re: Your account needs verification", "Urgent: verify your details within 24h to avoid suspension."),
    ("Crypto opportunity 🚀 10x returns", "Exclusive investment, act fast, guaranteed profits."),
]
SENT_SUBJECTS = [
    "Following up on our conversation", "Proposal attached", "Re: Pricing question",
    "Meeting notes", "Quick question about the API", "Thanks for the demo",
    "Contract for signature", "Re: Renewal terms",
]
DRAFTS = [
    ("Re: Q3 partnership proposal", "Hi — circling back on the revenue share. I think we're close; let me loop in finance and..."),
    ("Intro to the team", "Hi all, wanted to introduce myself ahead of next week's kickoff. I'll be your main point of..."),
]


def _dt(days_ago, hour=None):
    h = hour if hour is not None else RNG.randint(7, 20)
    return (NOW - timedelta(days=days_ago)).replace(hour=h, minute=RNG.randint(0, 59), second=0).strftime("%Y-%m-%d %H:%M:%S")


def _snippet(body):
    return body.replace("\n", " ").strip()[:110]


def build():
    db.init_schema()
    with db.cursor() as conn:
        for t in ("message_labels", "labels", "events", "messages", "contacts", "chat_messages"):
            conn.execute(f"DELETE FROM {t}")
        conn.executemany("INSERT INTO contacts(name,email,company) VALUES (?,?,?)", PEOPLE)

    msgs = []
    tid = 0
    # Inbox threads
    for subj, turns in INBOX_THREADS:
        tid += 1
        person = RNG.choice(PEOPLE)
        first = person[0].split()[0]
        days = RNG.randint(0, 12)
        for i, (who, body) in enumerate(turns):
            day = days - i * RNG.choice([0, 1])
            day = max(0, day)
            body = body.format(name=person[0], first=first)
            if who == "them":
                folder = "Inbox"
                fn, fe = person[0], person[1]
                tn, te = ME
            else:
                folder = "Sent"
                fn, fe = ME
                tn, te = person[0], person[1]
            is_read = 1 if (folder == "Sent" or RNG.random() < 0.55) else 0
            msgs.append((tid, folder, fn, fe, tn, te, subj if i == 0 else f"Re: {subj}",
                         body, _snippet(body), _dt(day), is_read,
                         1 if RNG.random() < 0.25 else 0, 1 if RNG.random() < 0.2 else 0))

    # extra inbox singletons
    for subj, body_t in [("Your monthly report is ready", "Hi Avery, your usage report for May is ready to download from the dashboard."),
                         ("Team offsite — save the date", "We're planning the summer offsite for July 18-19. Please hold the dates!"),
                         ("Action required: update billing card", "Your card on file expires this month. Please update it to avoid interruption."),
                         ("Welcome to the beta", "You're in! Here's how to get started with the new analytics beta.")]:
        tid += 1
        p = RNG.choice(PEOPLE)
        msgs.append((tid, "Inbox", p[0], p[1], *ME, subj, body_t, _snippet(body_t),
                     _dt(RNG.randint(0, 20)), 1 if RNG.random() < 0.5 else 0,
                     1 if RNG.random() < 0.2 else 0, 0))

    # Sent extras
    for subj in SENT_SUBJECTS:
        tid += 1
        p = RNG.choice(PEOPLE)
        body = f"Hi {p[0].split()[0]},\n\n{subj}. Let me know if that works for you.\n\nBest,\nAvery"
        msgs.append((tid, "Sent", *ME, p[0], p[1], subj, body, _snippet(body),
                     _dt(RNG.randint(0, 25)), 1, 0, 0))

    # Drafts
    for subj, body in DRAFTS:
        tid += 1
        p = RNG.choice(PEOPLE)
        msgs.append((tid, "Drafts", *ME, p[0], p[1], subj, body, _snippet(body),
                     _dt(RNG.randint(0, 4)), 1, 0, 0))

    # Archive
    for i in range(14):
        tid += 1
        p = RNG.choice(PEOPLE)
        subj = RNG.choice(["Re: Contract", "Notes from last quarter", "FYI", "Old thread", "Receipt", "Re: Scheduling"])
        body = "Archived message — kept for reference."
        msgs.append((tid, "Archive", p[0], p[1], *ME, subj, body, _snippet(body),
                     _dt(RNG.randint(30, 200)), 1, 0, 0))

    # Spam
    for subj, body in SPAM:
        tid += 1
        msgs.append((tid, "Spam", "Unknown Sender", "noreply@suspicious.example", *ME,
                     subj, body, _snippet(body), _dt(RNG.randint(0, 9)), 0, 0, 0))

    # Trash
    for i in range(5):
        tid += 1
        p = RNG.choice(PEOPLE)
        body = "Deleted message."
        msgs.append((tid, "Trash", p[0], p[1], *ME, "Re: Old request", body, _snippet(body),
                     _dt(RNG.randint(5, 40)), 1, 0, 0))

    with db.cursor() as conn:
        conn.executemany(
            """INSERT INTO messages
               (thread_id,folder,from_name,from_email,to_name,to_email,subject,body,snippet,
                sent_at,is_read,is_starred,has_attach)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", msgs)

    # labels
    labels = [("Work", "blue"), ("Personal", "green"), ("Finance", "amber"),
              ("Travel", "teal"), ("Important", "red"), ("Newsletter", "purple")]
    with db.cursor() as conn:
        conn.executemany("INSERT INTO labels(name,color) VALUES (?,?)", labels)
        label_ids = [r[0] for r in conn.execute("SELECT id FROM labels").fetchall()]
        inbox_ids = [r[0] for r in conn.execute(
            "SELECT id FROM messages WHERE folder='Inbox'").fetchall()]
        # tag ~60% of inbox messages with 1–2 random labels
        ml = []
        for mid in inbox_ids:
            if RNG.random() < 0.6:
                for lid in RNG.sample(label_ids, RNG.randint(1, 2)):
                    ml.append((mid, lid))
        conn.executemany("INSERT OR IGNORE INTO message_labels(message_id,label_id) VALUES (?,?)", ml)

    # calendar events around the 'today' (2026-06-11)
    ev_titles = [
        ("Team standup", "09:00", "Zoom", "blue"), ("1:1 with Morgan", "11:30", "Office 3B", "purple"),
        ("Product review", "14:00", "Boardroom", "blue"), ("Dentist", "08:30", "High St Clinic", "green"),
        ("Flight to Berlin", "06:45", "LHR T5", "teal"), ("Quarterly board", "10:00", "HQ", "red"),
        ("Lunch with Sam", "12:30", "Café Nero", "green"), ("Invoice run", "16:00", "", "amber"),
        ("Design crit", "15:00", "Studio", "blue"), ("Gym", "18:30", "", "green"),
        ("Customer demo", "13:00", "Zoom", "blue"), ("Payroll cutoff", "17:00", "", "amber"),
    ]
    events = []
    for (title, hm, loc, color) in ev_titles:
        day_offset = RNG.randint(-3, 18)  # spread across the visible month
        d = (NOW + timedelta(days=day_offset)).date()
        events.append((title, f"{d.isoformat()} {hm}", None, loc or None, None, color))
    with db.cursor() as conn:
        conn.executemany(
            "INSERT INTO events(title,start_at,end_at,location,notes,color) VALUES (?,?,?,?,?,?)", events)

    print(f"FastMail seeded → {db.DB_PATH}")
    print(f"  {len(msgs)} messages across {len(db.FOLDERS)} folders · {len(PEOPLE)} contacts")
    print(f"  {len(labels)} labels · {len(ml)} label tags · {len(events)} calendar events")


if __name__ == "__main__":
    build()
