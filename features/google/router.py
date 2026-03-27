"""
Route voice text to Google Calendar, Docs, Gmail. Returns voice string or None.
"""
import logging
import re
from datetime import datetime, timedelta, timezone

import requests

from core import config
from features.google import auth, calendar, docs, gmail

logger = logging.getLogger(__name__)

GMAIL_PATTERNS = re.compile(
    r"\b(gmail|email|emails|inbox|teacher\s+emailed|check\s+my\s+mail|anything\s+important)\b",
    re.I,
)
DOCS_WRITE_PATTERNS = re.compile(
    r"\b(write\s+me\s+an?\s+|create\s+(notes|a\s+document|a\s+report)|essay\s+about|report\s+on|document\s+about)\b",
    re.I,
)
DOCS_EDIT_PATTERNS = re.compile(r"\b(update|edit|change)\s+(my\s+)?(essay|document|intro|paper)\b", re.I)
CAL_PATTERNS = re.compile(
    r"\b(calendar|what'?s\s+due|due\s+this\s+week|due\s+friday|add\s+.*\s+due|schedule)\b",
    re.I,
)


def _ollama(system: str, user: str) -> str:
    url = f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "options": {"num_predict": getattr(config, "OLLAMA_NUM_PREDICT", 256)},
    }
    try:
        r = requests.post(url, json=payload, timeout=config.OLLAMA_TIMEOUT)
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
            return _handle_gmail()
        if DOCS_EDIT_PATTERNS.search(t):
            return _handle_docs_edit(t)
        if DOCS_WRITE_PATTERNS.search(t) or re.search(r"\b(write|create)\b.*\b(about|on)\b", t, re.I):
            return _handle_docs_write(t)
        if CAL_PATTERNS.search(t) or re.search(r"\bdue\s+", t, re.I):
            return _handle_calendar(t)
    except Exception as e:
        logger.exception("Google router: %s", e)
        return auth.google_error_message()
    return None


def _handle_gmail() -> str:
    items = gmail.list_unread(10)
    if not items:
        return "You have no unread emails in your inbox."
    lines = []
    for m in items:
        lines.append(f"From: {m['from']}\nSubject: {m['subject']}\nSnippet: {m['snippet']}")
    blob = "\n---\n".join(lines)
    sys = """You summarize email for voice. Reply in 2-4 short sentences only.
Mention only important school-related or personal emails; ignore obvious spam and promotions.
Never quote full bodies. Sound natural."""
    out = _ollama(sys, f"Summarize these for the student:\n{blob}")
    if not out:
        return auth.google_error_message()
    return out


def _handle_docs_write(user_text: str) -> str:
    sys = """You write complete school essays, notes, or reports. Output only the document body.
Use clear paragraphs. No meta-commentary."""
    body = _ollama(sys, user_text)
    if not body:
        return auth.google_error_message()
    title = _ollama(
        "Reply with a 5-word or fewer title only, no quotes.",
        f"Title for: {user_text[:200]}",
    )[:80] or "Zap Document"
    doc_id, link = docs.create_document(title.strip(), body)
    docs.open_in_browser(link)
    return f"I created a Google Doc titled {title.strip()}. Opening it in your browser."


def _handle_docs_edit(user_text: str) -> str:
    doc_id = docs.get_recent_doc_id()
    if not doc_id:
        return "I don't have a recent document to edit. Ask me to write something first."
    sys = """You revise or add to a student document. Output only the new or replacement text."""
    new_part = _ollama(sys, user_text)
    if not new_part:
        return auth.google_error_message()
    docs.update_document_body(doc_id, "\n\n" + new_part, replace_all=False)
    link = f"https://docs.google.com/document/d/{doc_id}/edit"
    docs.open_in_browser(link)
    return "I updated your document. Opening it now."


def _handle_calendar(user_text: str) -> str:
    try:
        import dateparser
    except ImportError:
        dateparser = None

    low = user_text.lower()
    if "what" in low or "due this week" in low or "this week" in low:
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=7)
        evs = calendar.list_events(now, end)
        return calendar.format_events_for_voice(evs)

    if "add" in low or "create" in low or "schedule" in low:
        extract = _ollama(
            """Extract calendar event. Reply EXACTLY in two lines:
Line1: short title (max 60 chars)
Line2: ISO 8601 datetime in UTC for START (e.g. 2026-03-20T15:00:00+00:00)
If you cannot parse a time, use tomorrow 3pm UTC.""",
            user_text,
        )
        lines = [ln.strip() for ln in extract.split("\n") if ln.strip()]
        if len(lines) < 2:
            return "I couldn't figure out when that event should be. Try saying the day and time clearly."
        title = lines[0]
        start = None
        try:
            start = datetime.fromisoformat(lines[1].replace("Z", "+00:00"))
        except Exception:
            pass
        if start is None and dateparser:
            start = dateparser.parse(user_text, settings={"RETURN_AS_TIMEZONE_AWARE": True})
        if start is None:
            return "I couldn't parse the date. Try again with a clear day and time."
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        calendar.create_event(title, start)
        return f"Added to your calendar: {title}."

    return calendar.format_events_for_voice(
        calendar.list_events(datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(days=7))
    )


def refresh_cache() -> None:
    """Preload counts for planning (optional)."""
    try:
        calendar.list_events(
            datetime.now(timezone.utc),
            datetime.now(timezone.utc) + timedelta(days=1),
        )
        gmail.list_unread(1)
    except Exception:
        pass
