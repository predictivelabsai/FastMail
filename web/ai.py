"""FastMail AI — grounded chat, slash-commands, thread summarise & draft reply."""
from __future__ import annotations

import json
import os

import db

PROVIDER = os.getenv("MODEL_PROVIDER", "xai")
MODEL = os.getenv("MODEL_NAME", "grok-4-1-fast-reasoning")


def snapshot() -> str:
    counts = db.folder_counts()
    unread = db.rows("SELECT from_name, subject, snippet FROM messages WHERE folder='Inbox' AND is_read=0 ORDER BY sent_at DESC LIMIT 12")
    lines = [f"MAILBOX SNAPSHOT for {db.ACCOUNT_NAME} <{db.ACCOUNT_EMAIL}> (synthetic):",
             f"- Inbox: {counts['Inbox']['total']} ({counts['Inbox']['unread']} unread). "
             f"Drafts: {counts['Drafts']['total']}. Starred: {counts['Starred']['total']}."]
    if unread:
        lines.append("Unread inbox messages:")
        for m in unread:
            lines.append(f"  - {m['from_name']}: {m['subject']} — {m['snippet']}")
    return "\n".join(lines)


SYSTEM_PROMPT = """You are the FastMail assistant, embedded in a webmail client.
Help the user triage and respond to email. Be concise; use Markdown when it helps.
All mail is synthetic demo data — never claim it's real. Base answers on the MAILBOX
SNAPSHOT below; if something isn't there, say so."""


def _table(headers, rows_):
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for r in rows_:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def handle_command(text):
    if not text.startswith("/"):
        return None
    parts = text[1:].split()
    cmd = parts[0].lower() if parts else ""
    arg = " ".join(parts[1:])
    if cmd in ("help", "?"):
        return ("**FastMail shortcuts**\n\n- `/unread` — unread inbox messages\n"
                "- `/find <text>` — search your mail\n- `/starred` — starred messages\n\n"
                "Open a message to **summarise** the thread or **draft a reply** with AI.")
    if cmd == "unread":
        r = db.rows("SELECT from_name, subject FROM messages WHERE folder='Inbox' AND is_read=0 ORDER BY sent_at DESC")
        if not r:
            return "No unread messages. 📭"
        return "**Unread inbox**\n\n" + _table(["From", "Subject"], [[x["from_name"], x["subject"]] for x in r])
    if cmd == "starred":
        r = db.rows("SELECT from_name, subject FROM messages WHERE is_starred=1 AND folder!='Trash' ORDER BY sent_at DESC")
        return "**Starred**\n\n" + _table(["From", "Subject"], [[x["from_name"], x["subject"]] for x in r]) if r else "No starred messages."
    if cmd == "find":
        if not arg:
            return "Usage: `/find <text>`"
        r = db.rows("""SELECT from_name, subject, folder FROM messages
                       WHERE subject LIKE ? OR body LIKE ? OR from_name LIKE ? ORDER BY sent_at DESC LIMIT 15""",
                    (f"%{arg}%", f"%{arg}%", f"%{arg}%"))
        if not r:
            return f"No messages matching '{arg}'."
        return f"**Results for '{arg}'**\n\n" + _table(["From", "Subject", "Folder"],
                                                       [[x["from_name"], x["subject"], x["folder"]] for x in r])
    return f"Unknown command `/{cmd}`. Try `/help`."


# --- streaming chat ---------------------------------------------------------

async def stream_chat(message):
    cmd = handle_command(message)
    if cmd is not None:
        yield f"data: {json.dumps({'token': cmd})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
        return
    system = SYSTEM_PROMPT + "\n\n" + snapshot()
    try:
        async for tok in _provider_stream(system, message):
            yield f"data: {json.dumps({'token': tok})}\n\n"
    except Exception as e:  # noqa: BLE001
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    yield f"data: {json.dumps({'done': True})}\n\n"


# --- summarise / draft (non-streaming, return HTML-safe text) ---------------

def _need_key():
    env = {"xai": "XAI_API_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "google": "GOOGLE_API_KEY"}.get(PROVIDER)
    if not env or not os.getenv(env):
        raise RuntimeError(f"No {env or 'LLM'} key set — add it to .env to use AI summarise/draft.")


def summarise_thread(thread_id: int, fallback_mid: int) -> str:
    _need_key()
    msgs = db.thread(thread_id) if thread_id else [db.message(fallback_mid)]
    convo = "\n\n".join(f"From {m['from_name']} ({m['sent_at'][:16]}):\n{m['body']}" for m in msgs if m)
    out = _complete("Summarise this email thread in 2-3 short bullet points, then one line: "
                    "'Suggested action:'. Be concise and concrete.", convo)
    return _html_para(out)


def draft_reply(mid: int) -> str:
    _need_key()
    m = db.message(mid)
    if not m:
        return "Message not found."
    out = _complete(
        f"You are {db.ACCOUNT_NAME}. Write a brief, friendly, professional reply to the email below. "
        "Output only the reply body (no subject, no signature beyond '— Avery').",
        f"From {m['from_name']}:\nSubject: {m['subject']}\n\n{m['body']}")
    return _html_para(out)


def _html_para(text: str) -> str:
    import html
    return html.escape(text).replace("\n", "<br>")


# --- providers --------------------------------------------------------------

def _complete(system: str, user: str) -> str:
    import httpx
    provider, model = PROVIDER, MODEL
    if provider in ("xai", "openai"):
        url = "https://api.x.ai/v1/chat/completions" if provider == "xai" else "https://api.openai.com/v1/chat/completions"
        key = os.getenv("XAI_API_KEY" if provider == "xai" else "OPENAI_API_KEY", "")
        r = httpx.post(url, headers={"Authorization": f"Bearer {key}"},
                       json={"model": model, "messages": [{"role": "system", "content": system},
                                                          {"role": "user", "content": user}]}, timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    if provider == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY", "")
        r = httpx.post("https://api.anthropic.com/v1/messages",
                       headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                       json={"model": model, "max_tokens": 700, "system": system,
                             "messages": [{"role": "user", "content": user}]}, timeout=60)
        r.raise_for_status()
        return r.json()["content"][0]["text"].strip()
    if provider == "google":
        key = os.getenv("GOOGLE_API_KEY", "")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        r = httpx.post(url, json={"system_instruction": {"parts": [{"text": system}]},
                                  "contents": [{"role": "user", "parts": [{"text": user}]}]}, timeout=60)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    raise RuntimeError(f"Unsupported provider '{provider}'.")


async def _provider_stream(system, message):
    import httpx
    provider, model = PROVIDER, MODEL
    if provider in ("xai", "openai"):
        url = "https://api.x.ai/v1/chat/completions" if provider == "xai" else "https://api.openai.com/v1/chat/completions"
        key = os.getenv("XAI_API_KEY" if provider == "xai" else "OPENAI_API_KEY", "")
        if not key:
            yield _no_key(provider); return
        async with httpx.AsyncClient(timeout=90) as client:
            async with client.stream("POST", url, headers={"Authorization": f"Bearer {key}"},
                                     json={"model": model, "stream": True,
                                           "messages": [{"role": "system", "content": system},
                                                        {"role": "user", "content": message}]}) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            tok = json.loads(line[6:])["choices"][0]["delta"].get("content", "")
                            if tok: yield tok
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass
    elif provider == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            yield _no_key(provider); return
        async with httpx.AsyncClient(timeout=90) as client:
            async with client.stream("POST", "https://api.anthropic.com/v1/messages",
                                     headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
                                     json={"model": model, "max_tokens": 1500, "stream": True, "system": system,
                                           "messages": [{"role": "user", "content": message}]}) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            ev = json.loads(line[6:])
                            if ev.get("type") == "content_block_delta":
                                tok = ev.get("delta", {}).get("text", "")
                                if tok: yield tok
                        except json.JSONDecodeError:
                            pass
    elif provider == "google":
        key = os.getenv("GOOGLE_API_KEY", "")
        if not key:
            yield _no_key(provider); return
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={key}"
        async with httpx.AsyncClient(timeout=90) as client:
            async with client.stream("POST", url, json={"system_instruction": {"parts": [{"text": system}]},
                                                        "contents": [{"role": "user", "parts": [{"text": message}]}]}) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            tok = json.loads(line[6:])["candidates"][0]["content"]["parts"][0].get("text", "")
                            if tok: yield tok
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass
    else:
        yield "No LLM provider configured. Slash-commands like /unread work without a key."


def _no_key(provider):
    env = {"xai": "XAI_API_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "google": "GOOGLE_API_KEY"}[provider]
    return (f"⚠ No **{env}** set, so free-form chat is disabled. Add it to `.env` and restart. "
            "Slash-commands (`/unread`, `/find`, `/starred`) work without any key.")
