# Skills

Capability reference for FastMail + the shared **Frappe → FastHTML migration
playbook** (same recipe across `fasthtml-oss-migrations`; see `FastCRM/SKILLS.md`).

---

## Part 1 — FastMail capabilities

**Entry:** `python web_app.py` → http://localhost:5009
(login `admin@fastmail.example` / `FastMail2026$`).

### Pages

| View | Route | What it shows |
|---|---|---|
| Folder | `/folder/{folder}?q=` | message list (Inbox/Starred/Sent/Drafts/Archive/Spam/Trash) |
| Message | `/message/{id}` | threaded reading pane + AI buttons |
| Compose | `/compose?reply={id}` | new message / reply |
| Contacts | `/contacts` | address book |
| AI Assistant | `/ai` | chat (right rail) |

### Interactions

- **Inline star** — `POST /star/{id}` returns just the star cell (`hx-swap=outerHTML`).
- **Send** — `POST /send` appends to Sent and rebuilds the compose view.
- **AI summarise** — `POST /ai/summarise/{thread}/{mid}` → swaps an `#ai-panel`.
- **AI draft** — `POST /ai/draft/{mid}` → swaps an `#ai-panel`.

### AI (`web/ai.py`)

- `summarise_thread()` / `draft_reply()` — non-streaming `_complete()` calls.
- **Grounded chat** — streamed with a live mailbox snapshot.
- **Slash-commands** (no key): `/unread`, `/find <text>`, `/starred`.

### Data (`db.py`)

`messages` (folder, thread_id, from/to, body, flags) · `contacts` · `chat_messages`.
`folder_counts()` powers the sidebar badges. Rebuild with `python seed.py`.

---

## Part 2 — Frappe → FastHTML migration playbook

1. **Mine the schema** — `python scripts/frappe_doctype_to_schema.py /tmp/frappe-mail`.
2. **Pick the client slice** — Frappe Mail is a server platform; FastMail ports
   only the webmail *client* (folders/messages/threads/contacts). Scope ruthlessly.
3. **FastHTML shell** — `fast_app(pico=False, hdrs=[Style(CSS)])`; a `page()`
   wrapper that here also takes **folder counts** so the nav badges are live.
4. **HTMX over JS** — inline star toggle and AI panels are `hx-post` + targeted
   swaps; the reading pane is a normal navigation.
5. **Synthetic data** — fixed RNG seed; realistic thread content; self-seed on boot.
6. **LLM, key-optional** — `_complete()` (summarise/draft) + `_provider_stream()`
   (chat); slash-commands work with no key.
7. **Capture the demo** — Playwright MCP → frames → `build_demo_gif.sh`.
8. **Ship deploy paths** — `.env.sample`, `Dockerfile`, `docker-compose.yml`.

### Reusable assets

| File | Reuse |
|---|---|
| `scripts/frappe_doctype_to_schema.py` | DocType JSON → SQLite DDL |
| `scripts/build_demo_gif.sh` | frames → demo GIF |
| `web/ai.py` `summarise_*` / `draft_*` | per-item LLM actions swapped via HTMX |
| `web/layout.py` | 3-pane shell + CSS tokens + SSE chat JS |
