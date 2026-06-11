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
| **AI summarise / draft** | *(not upstream)* | per-thread summary + reply draft |

## Near-term roadmap 🔜

1. **Real reply/forward send flow** — currently compose saves to Sent; wire
   reply/forward to thread the new message and update folder counts live.
2. **Labels / multiple accounts** — `Identity`, `Mailbox Settings` (more than
   one identity, custom labels beyond the 6 system folders).
3. **Search operators** — `from:`, `subject:`, `is:unread`, date ranges.
4. **Calendar** — `frappe/mail` bundles a calendar subsystem (`Calendar`,
   `Calendar Event`, `Event Participant`). Add a calendar + event views as a
   second module (the 3-pane shell already suits it).
5. **Attachments** — `Mail Message Part` (show/download attachments;
   `has_attach` is modelled but inert).
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
(summarise/draft) that a traditional webmail lacks. The most valuable next step
is the **calendar** module — upstream ships it inside `frappe/mail`, and the
3-pane shell already accommodates a calendar/agenda view.
