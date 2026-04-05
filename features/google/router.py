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
    r"\b(calendar|google\s+calendar|cal\s+event|what'?s\s+due|due\s+this\s+week|due\s+friday|"
    r"add\s+.*\s+due|schedule)\b",
    re.I,
)
# Create before list — matches "create a calendar…", "add … due tomorrow…", "schedule …"
_CAL_CREATE_VERB = re.compile(
    r"\b(add|create|scheduled?|schedule|book|set\s+up|remind\s+me|put)\b",
    re.I,
)


def _wants_calendar_create(low: str) -> bool:
    """True when user intends to add an event (must run before 'tomorrow' list)."""
    if _CAL_CREATE_VERB.search(low):
        return True
    if re.search(r"\b(make|new)\s+(an?\s+)?(event|reminder|appointment)\b", low):
        return True
    return False


_HOUR_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}


def _prepare_calendar_datetime_text(raw: str) -> str:
    """Make STT phrases parse reliably: 'eight a.m.' → '8 am', 'tomorrow at 8' → 'tomorrow at 8 am'."""
    s = raw.strip()

    def _repl_spoken_hour(m: re.Match) -> str:
        w = m.group(1).lower()
        n = _HOUR_WORDS.get(w)
        if n is None:
            return m.group(0)
        ampm = (m.group(2) or "").strip()
        return f"at {n} {ampm}".strip() if ampm else f"at {n}"

    s = re.sub(
        r"\bat\s+(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
        r"(\s+(?:a\.?m\.?|p\.?m\.?))?\b",
        _repl_spoken_hour,
        s,
        flags=re.I,
    )

    def _spoken_ampm(m: re.Match) -> str:
        w = m.group(1).lower()
        n = _HOUR_WORDS.get(w)
        if n is None:
            return m.group(0)
        ap = m.group(2).replace(".", "").lower()
        if ap.startswith("a"):
            return f"{n} am"
        return f"{n} pm"

    s = re.sub(
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+"
        r"(a\.?m\.?|p\.?m\.?)\b",
        _spoken_ampm,
        s,
        flags=re.I,
    )

    def _tomorrow_at_hour(m: re.Match) -> str:
        day, hour_s, ampm = m.group(1), m.group(2), m.group(3)
        if ampm:
            return m.group(0)
        h = int(hour_s)
        if 1 <= h <= 11:
            return f"{day} at {h} am"
        if h == 12:
            return f"{day} at 12 pm"
        return m.group(0)

    s = re.sub(
        r"\b(tomorrow|today)\s+at\s+(\d{1,2})(\s+(?:a\.?m\.?|p\.?m\.?))?\b",
        _tomorrow_at_hour,
        s,
        flags=re.I,
    )
    return s


def _extract_calendar_title(user_text: str) -> str:
    """Pull title from '… about my math homework' or '… for math homework …'."""
    t = user_text.strip()
    m = re.search(
        r"\babout\s+(.+?)(?:\s*[,.])?\s*$",
        t,
        re.I,
    )
    if m:
        return m.group(1).strip()[:120]
    m = re.search(
        r"\babout\s+(.+?)(?=\s+(?:tomorrow|today|at\s|@|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b)",
        t,
        re.I,
    )
    if m:
        return m.group(1).strip()[:120]
    m = re.search(r"\bfor\s+(?:my\s+)?(.+?)(?=\s+(?:tomorrow|today|at\s|@)\b)", t, re.I)
    if m:
        return m.group(1).strip()[:120]
    return ""


def _normalize_event_start(start: datetime) -> datetime:
    """Interpret naive times and convert to UTC for Google Calendar."""
    if start.tzinfo is not None:
        return start.astimezone(timezone.utc)
    tzname = getattr(config, "LOCAL_TIMEZONE", "").strip()
    if tzname:
        try:
            from zoneinfo import ZoneInfo

            return start.replace(tzinfo=ZoneInfo(tzname)).astimezone(timezone.utc)
        except Exception as e:
            logger.warning("LOCAL_TIMEZONE %s: %s", tzname, e)
    try:
        from datetime import datetime as _dt

        local = _dt.now().astimezone().tzinfo
        if local is not None:
            return start.replace(tzinfo=local).astimezone(timezone.utc)
    except Exception:
        pass
    return start.replace(tzinfo=timezone.utc)


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
    low = t.lower()
    cal_hit = bool(CAL_PATTERNS.search(t) or re.search(r"\bdue\s+", t, re.I))

    try:
        if GMAIL_PATTERNS.search(t):
            return _bg(_handle_gmail)
        if DOCS_EDIT_PATTERNS.search(t):
            return _bg(_handle_docs_edit, t)
        # Calendar create/list before Docs — "create a calendar on …" must not match write … on …
        if cal_hit and _wants_calendar_create(low):
            return _bg(_handle_calendar, t)
        if DOCS_WRITE_PATTERNS.search(t) or re.search(
            r"\b(write|create|make)\b.*\b(about|on)\b", t, re.I
        ):
            return _bg(_handle_docs_write, t)
        if cal_hit:
            return _bg(_handle_calendar, t)
    except Exception as e:
        logger.exception("Google router: %s", e)
        return auth.google_error_message()
    return None


def _handle_gmail() -> str:
    console_ui.intent_line("Google Gmail → priority sort + voice summary (LLM)")
    n = min(8, max(3, int(config.GMAIL_UNREAD_MAX)))
    items = gmail.list_unread(n)
    if not items:
        return "You have no unread emails in your inbox."
    # No sender names in the prompt — avoids the model reading "From: …" aloud
    lines = []
    for i, m in enumerate(items, 1):
        subj = (m.get("subject") or "").strip()
        snip = (m.get("snippet") or "")[:400]
        lines.append(f"[{i}] {subj}\n    preview: {snip}")
    blob = "\n".join(lines)
    sys = """You help a student triage unread email for VOICE output only.

Step 1 — mentally rank items 1..n by importance for school (deadlines, grades, teachers, assignments first; newsletters and ads last).

Step 2 — reply in at most 2 short sentences with ONLY a merged summary of what matters.
- Say what they should do or know (e.g. a deadline, homework, exam), in plain language.
- Do NOT say "email", "inbox", "subject line", or any sender names or email addresses.
- Do NOT list messages one by one. Do NOT read who sent what."""
    max_tok = getattr(config, "OLLAMA_NUM_PREDICT_GMAIL", 96)
    out = _ollama(
        sys,
        f"Unread items (most important first by number):\n{blob}",
        extended_timeout=True,
        max_tokens=max_tok,
    )
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

    if re.search(r"\b(move|reschedule|shift)\b", low):
        console_ui.intent_line("Google Calendar → move / reschedule event (match + update)")
        hint = _ollama(
            "Reply with 4-8 words: the event title or subject to find (homework name). No quotes.",
            user_text,
            max_tokens=64,
        )
        evs = calendar.find_upcoming_events_matching(hint)
        if not evs:
            return "I couldn't find that on your calendar. Try being more specific."
        ev = evs[0]
        new_start = None
        dp_settings: dict = {"RETURN_AS_TIMEZONE_AWARE": True, "PREFER_DATES_FROM": "future"}
        tz = getattr(config, "LOCAL_TIMEZONE", "").strip()
        if tz:
            dp_settings["TIMEZONE"] = tz
        if dateparser:
            new_start = dateparser.parse(
                _prepare_calendar_datetime_text(user_text),
                settings=dp_settings,
            )
        if new_start is None:
            return "Say when to move it to, like Saturday at 3 PM."
        new_start = _normalize_event_start(new_start)
        eid = ev.get("id")
        if not eid:
            return auth.google_error_message()
        calendar.update_event(str(eid), start=new_start)
        summ = ev.get("summary", "Event")
        return f"Done, I've moved {summ} to when you asked."

    if _wants_calendar_create(low):
        console_ui.intent_line("Google Calendar → create event (natural language → API)")
        parse_text = _prepare_calendar_datetime_text(user_text)
        extract = _ollama(
            """From the user's words, extract ONE calendar event.
Reply EXACTLY two lines (no extra text):
Line1: Short event title only (e.g. Math homework). Use their topic/homework if they said "about …".
Line2: Start datetime in ISO 8601 WITH timezone offset if you can, e.g. 2026-04-06T08:00:00-07:00
If they said tomorrow at 8 or eight in the morning, that is 8:00 AM local that day.""",
            parse_text,
            max_tokens=128,
        )
        lines = [ln.strip() for ln in extract.split("\n") if ln.strip()]
        title = (lines[0] if lines else "") or ""
        fallback_title = _extract_calendar_title(user_text)
        if not title or len(title) < 2 or title.lower() in ("reminder", "event", "calendar"):
            title = fallback_title or "Reminder"
        start = None
        if len(lines) >= 2:
            try:
                start = datetime.fromisoformat(lines[1].replace("Z", "+00:00"))
            except Exception:
                pass
        dp_settings = {"RETURN_AS_TIMEZONE_AWARE": True, "PREFER_DATES_FROM": "future"}
        tz = getattr(config, "LOCAL_TIMEZONE", "").strip()
        if tz:
            dp_settings["TIMEZONE"] = tz
        if start is None and dateparser:
            start = dateparser.parse(parse_text, settings=dp_settings)
        if start is None and dateparser:
            start = dateparser.parse(user_text, settings=dp_settings)
        if start is None:
            return (
                "I couldn't parse the date and time. Say it like: "
                "tomorrow at eight AM, or tomorrow at eight."
            )
        start = _normalize_event_start(start)
        calendar.create_event(title.strip() or "Reminder", start)
        return f"Done, I've added {title.strip() or 'that'} to your calendar."

    if re.search(r"\b(this\s+week|due\s+this\s+week)\b", low) and "tomorrow" not in low:
        console_ui.intent_line("Google Calendar → list / summarize this week")
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=7)
        evs = calendar.list_events(now, end)
        return calendar.format_events_conversational(
            evs,
            "This week you have:",
        )

    if "tomorrow" in low:
        console_ui.intent_line("Google Calendar → list events for tomorrow")
        evs = calendar.list_tomorrow_events()
        return calendar.format_events_conversational(
            evs,
            "Here's what you have tomorrow.",
        )

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
            gmail.list_unread(min(8, max(3, int(getattr(config, "GMAIL_UNREAD_MAX", 6)))))
        except Exception:
            pass

    _POOL.submit(run)
