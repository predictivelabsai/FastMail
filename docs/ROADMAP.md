# FastMail Roadmap — Frappe Mail feature comparison

`frappe/mail` (~52 doctypes) is a full **mail server platform**: SMTP/IMAP
accounts, message queues, server clusters, DNS/deliverability records, plus a
calendar subsystem. FastMail demonstrates the **webmail client** half over a
synthetic mailbox — the part a user actually sees.

## Implemented ✅

| Capability | Upstream area | FastMail |
|---|---|---|
| Mailbox / folders | `Mailbox`, `Mail Account` | `messages.folder` (Inbox/Sent/Drafts/Archive/Spam/Trash) |
| Messages | `Mail Message`/`Recipient`/`Part` | `messages` table |
| Threads | message references | `messages.thread_id` + threaded reading pane |
| Address book | `Address Book`, `Contact Card` | `contacts` |
| Compose / send | outbound message | `/compose` → saves to Sent |
| Star / read state | flags | inline HTMX star, read tracking |
| **Labels** | custom labels | `labels`/`message_labels` (colour chips, per-message add/remove, label views) |
| **Search operators** | query syntax | `from: to: subject: label: in: is:unread is:starred has:attachment` + free text |
| **Calendar** | `Calendar Event` | `events` table, month grid + day panel + create/delete |
| **AI summarise / draft** | *(not upstream)* | per-thread summary + reply draft |

## Near-term roadmap 🔜

1. ✅ **Reply send flow** (done) — inline threaded reply; wire
   reply/forward to thread the new message and update folder counts live.
2. ✅ **Labels** (done) — coloured custom labels (`labels`/`message_labels`):
   sidebar list with counts, per-message add/remove, dedicated label views, and
   a labels manager. Multiple identities/accounts are still out of scope.
3. ✅ **Search operators** (done) — a Gmail-style parser (`db.parse_search`):
   `from:` `to:` `subject:` `label:` `in:` `is:unread/read/starred`
   `has:attachment`, combinable with free text. Date-range operators still to come.
4. ✅ **Calendar** (done) — an `events` table with a month-grid view (today
   highlighted, prev/next navigation), a day/upcoming side panel, and
   create/delete. Event participants & invitations are still to come.
5. **Attachments** — `Mail Message Part` (show/download attachments;
   `has_attach` is modelled and now shown in the list, but inert).
6. **Rules / filters** — auto-file incoming mail by sender/subject.

## Later / out-of-scope 🗓️

The entire **server** side of Frappe Mail is intentionally out of scope for a
client demonstrator:

- **SMTP/IMAP delivery** — `Mail Server`, `Mail Agent`, `Mail Queue`,
  `Outgoing/Incoming Mail` (actually sending/receiving over the wire).
- **Deliverability** — `DNS Record`, `Mail Exchange`, SPF/DKIM/DMARC,
  `Mail Cluster`/`Store` (multi-node storage).
- **Quotas & rate limits** — `Quota`, `Rate Limit`, `Blocked Email Address`.
- **Account provisioning** — `Mail Account Request`, `Account Settings`.

## Design notes

FastMail is deliberately the **client**: it renders a mailbox and adds AI triage
(summarise/draft) that a traditional webmail lacks. It now also carries the
organisational layer on top of the mailbox — **labels** (colour-coded, many-to-
many), a **search-operator** parser that compiles a Gmail-style query to safe
parameterised SQL, and a **calendar** module (the `events` table + a month grid),
all sharing the same 3-pane HTMX shell.
