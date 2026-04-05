"""
Route voice text to Google Calendar, Docs, Gmail. Returns voice string or None.
Heavy API calls run in a thread pool so the mic pipeline stays responsive.
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import requests

from core import config
from core import console_ui
from features.google import auth, calendar, docs, gmail

logger = logging.getLogger(__name__)

_POOL = ThreadPoolExecutor(max_workers=6, thread_name_prefix="zap_google")

GMAIL_PATTERNS = re.compile(
    r"\b(gmail|email|emails|inbox|anything\s+important\s+in\s+my\s+email|"
    r"did\s+my\s+teacher\s+email|check\s+my\s+emails?|teacher\s+emailed)\b",
    re.I,
)
DOCS_WRITE_PATTERNS = re.compile(
    r"\b(write\s+me\s+an?\s+|create\s+(notes|a\s+document|a\s+report)|"
    r"essay\s+about|report\s+on|document\s+about|make\s+a\s+report)\b",
    re.I,
)
DOCS_EDIT_PATTERNS = re.compile(
    r"\b(update|edit|change)\s+(my\s+)?(essay|document|intro|paper|doc)\b",
    re.I,
)
CAL_PATTERNS = re.compile(
    r"\b(calendar|what'?s\s+due|due\s+this\s+week|due\s+friday|add\s+.*\s+due|schedule)\b",
    re.I,
)


def _bg(fn, *args, **kwargs):
    # Must exceed OLLAMA_TIMEOUT_GOOGLE + time for Docs API batch calls
    wait = max(300, int(config.OLLAMA_TIMEOUT_GOOGLE) + 120)
    return _POOL.submit(lambda: fn(*args, **kwargs)).result(timeout=wait)


def _ollama(
    system: str,
    user: str,
    *,
    long_body: bool = False,
    max_tokens: int | None = None,
    extended_timeout: bool = False,
) -> str:
    if max_tokens is not None:
        np = max_tokens
    elif long_body:
        np = config.OLLAMA_NUM_PREDICT_GOOGLE
    else:
        np = config.OLLAMA_NUM_PREDICT_ROUTER
    use_google_timeout = (
        long_body
        or extended_timeout
        or (max_tokens is not None and max_tokens >= 512)
    )
    timeout = config.OLLAMA_TIMEOUT_GOOGLE if use_google_timeout else config.OLLAMA_TIMEOUT
    temp = 0.45 if long_body or (max_tokens is not None and max_tokens >= 512) else 0.35
    url = f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "options": {"num_predict": np, "temperature": temp, "top_k": 32},
    }
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        return (r.json().get("message") or {}).get("content", "").strip()
    except Exception as e:
        logger.exception("Ollama helper failed: %s", e)
        return ""


def try_google(user_text: str) -> str | None:
    if not (user_text or "").strip():
        return None
    t = user_text.strip()

    try:
        if GMAIL_PATTERNS.search(t):
            return _bg(_handle_gmail)
        if DOCS_EDIT_PATTERNS.search(t):
            return _bg(_handle_docs_edit, t)
        if DOCS_WRITE_PATTERNS.search(t) or re.search(
            r"\b(write|create|make)\b.*\b(about|on)\b", t, re.I
        ):
            return _bg(_handle_docs_write, t)
        if CAL_PATTERNS.search(t) or re.search(r"\bdue\s+", t, re.I):
            return _bg(_handle_calendar, t)
    except Exception as e:
        logger.exception("Google router: %s", e)
        return auth.google_error_message()
    return None


def _handle_gmail() -> str:
    console_ui.intent_line("Google Gmail → fetch unread + smart summary (LLM)")
    items = gmail.list_unread(10)
    if not items:
        return "You have no unread emails in your inbox."
    lines = []
    for m in items:
        lines.append(f"From: {m['from']}\nSubject: {m['subject']}\nSnippet: {m['snippet']}")
    blob = "\n---\n".join(lines)
    sys = """You summarize email for voice only. Reply in 2-4 short sentences.
Count important school-related emails; ignore spam and promotions.
Never quote full bodies. Example: You have 2 important emails — one from Mrs. Johnson about your project due Monday, and one from the school about picture day."""
    out = _ollama(sys, f"Summarize for the student:\n{blob}", extended_timeout=True)
    if not out:
        return auth.google_error_message()
    return out


def _handle_docs_write(user_text: str) -> str:
    console_ui.intent_line("Google Docs → create full document (Markdown → rich formatting + API)")
    sys = """You write complete school documents. Output ONLY the document body in Markdown:
- ## for main section titles
- ### for subsection titles
- **term** for bold important terms
- Normal paragraphs between sections (blank line between paragraphs)
Write the FULL assignment: introduction, body sections, and conclusion as appropriate. Do not stop early, do not summarize with "and so on", do not say you will continue later.
No meta-commentary before or after the Markdown. No outline-only — deliver complete prose."""
    body = _ollama(sys, user_text, long_body=True)
    if not body:
        return auth.google_error_message()
    title = _ollama(
        "Reply with a short document title only (max 8 words), no quotes. "
        "Example: World War II: A Global Conflict",
        user_text[:500],
    )
    title = (title or "Zap Document").strip()[:120]
    doc_id, link = docs.create_document_rich(title, body)
    console_ui.doc_created(title[:80])
    docs.open_in_browser(link)
    console_ui.doc_opened()
    short = title[:60]
    return (
        f"I've created your document in Google Docs titled {short} and opened it for you."
    )


def _handle_docs_edit(user_text: str) -> str:
    console_ui.intent_line("Google Docs → edit most recent document (append + API)")
    doc_id = docs.get_recent_doc_id()
    if not doc_id:
        return "I don't have a recent document to edit. Ask me to write something first."
    sys = """Output only the new text to append to the document. Use Markdown (## ### **) like create. Write the complete addition — do not truncate."""
    new_part = _ollama(sys, user_text, long_body=True)
    if not new_part:
        return auth.google_error_message()
    docs.update_document_body(doc_id, "\n\n" + new_part, replace_all=False)
    link = f"https://docs.google.com/document/d/{doc_id}/edit"
    docs.open_in_browser(link)
    console_ui.doc_opened()
    return "I've updated your document in Google Docs and opened it for you."


def _handle_calendar(user_text: str) -> str:
    try:
        import dateparser
    except ImportError:
        dateparser = None

    low = user_text.lower()

    if "tomorrow" in low or "anything tomorrow" in low:
        console_ui.intent_line("Google Calendar → list events for tomorrow")
        evs = calendar.list_tomorrow_events()
        return calendar.format_events_conversational(
            evs,
            "Here's what you have tomorrow.",
        )

    if re.search(r"\b(move|reschedule|shift)\b", low):
        console_ui.intent_line("Google Calendar → move / reschedule event (match + update)")
        hint = _ollama(
            "Reply with 4-8 words: the event title or subject to find (homework name). No quotes.",
            user_text,
        )
        evs = calendar.find_upcoming_events_matching(hint)
        if not evs:
            return "I couldn't find that on your calendar. Try being more specific."
        ev = evs[0]
        new_start = None
        if dateparser:
            new_start = dateparser.parse(user_text, settings={"RETURN_AS_TIMEZONE_AWARE": True})
        if new_start is None:
            return "Say when to move it to, like Saturday at 3 PM."
        if new_start.tzinfo is None:
            new_start = new_start.replace(tzinfo=timezone.utc)
        eid = ev.get("id")
        if not eid:
            return auth.google_error_message()
        calendar.update_event(str(eid), start=new_start)
        summ = ev.get("summary", "Event")
        return f"Done, I've moved {summ} to when you asked."

    if "what" in low or "due this week" in low or "this week" in low:
        console_ui.intent_line("Google Calendar → list / summarize this week")
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=7)
        evs = calendar.list_events(now, end)
        return calendar.format_events_conversational(
            evs,
            "This week you have:",
        )

    if "add" in low or "create" in low or "schedule" in low:
        console_ui.intent_line("Google Calendar → create event (natural language → API)")
        extract = _ollama(
            """Extract calendar event. Reply EXACTLY in two lines:
Line1: short title (max 60 chars)
Line2: ISO 8601 datetime in UTC for START (e.g. 2026-03-20T17:00:00+00:00)""",
            user_text,
        )
        lines = [ln.strip() for ln in extract.split("\n") if ln.strip()]
        if len(lines) < 2:
            return "I couldn't figure out when that event should be. Try again with day and time."
        title = lines[0]
        start = None
        try:
            start = datetime.fromisoformat(lines[1].replace("Z", "+00:00"))
        except Exception:
            pass
        if start is None and dateparser:
            start = dateparser.parse(user_text, settings={"RETURN_AS_TIMEZONE_AWARE": True})
        if start is None:
            return "I couldn't parse the date. Try something like Friday at 5 PM."
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        calendar.create_event(title, start)
        return f"Done, I've added {title} to your calendar."

    console_ui.intent_line("Google Calendar → list upcoming (next 7 days)")
    now = datetime.now(timezone.utc)
    evs = calendar.list_events(now, now + timedelta(days=7))
    return calendar.format_events_conversational(evs, "Upcoming:")


def refresh_cache() -> None:
    try:
        calendar.list_events(
            datetime.now(timezone.utc),
            datetime.now(timezone.utc) + timedelta(days=1),
        )
        gmail.list_unread(1)
    except Exception:
        pass


def prefetch_gmail_background() -> None:
    def run():
        try:
            gmail.list_unread(10)
        except Exception:
            pass

    _POOL.submit(run)
