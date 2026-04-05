"""
LLM with session history and planner command parsing.
Returns reply text for TTS; executes ADD/LIST/DONE/REMOVE from response.
Google Calendar/Docs/Gmail routed first when matched.
"""
import logging
import re
import requests
from typing import List, Tuple

from core import config
from features import planner
from features.google import router as google_router

logger = logging.getLogger(__name__)


def _truncate_voice(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return text
    m = config.VOICE_REPLY_MAX_CHARS
    if len(text) > m:
        return text[: m - 3] + "..."
    return text


_PLANNER_HINT = re.compile(
    r"\b(add|list|done|remove|homework|assignment|planner)\b",
    re.I,
)


def planner_likely(user_text: str) -> bool:
    """Sync path needed for ADD|LIST| planner lines."""
    return bool(_PLANNER_HINT.search(user_text or ""))


def _chat(messages: List[dict]) -> str:
    url = f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": [{"role": "system", "content": config.SYSTEM_PROMPT}] + messages,
        "stream": False,
        "options": {
            "num_predict": getattr(config, "OLLAMA_NUM_PREDICT", 64),
            "temperature": 0.35,
            "top_k": 32,
        },
    }
    try:
        r = requests.post(url, json=payload, timeout=config.OLLAMA_TIMEOUT)
        r.raise_for_status()
        return (r.json().get("message") or {}).get("content", "").strip()
    except requests.RequestException as e:
        logger.exception("Ollama request failed: %s", e)
        return ""


def _parse_planner_line(line: str) -> Tuple[str, list] | None:
    line = (line or "").strip()
    line_upper = line.upper()
    if line_upper == "LIST":
        return ("LIST", [])
    if line_upper.startswith("ADD|"):
        parts = line[4:].strip().split("|")
        if len(parts) >= 4:
            return ("ADD", [p.strip() for p in parts[:4]])
        if len(parts) == 1 and parts[0]:
            return ("ADD", [parts[0], "Homework", "tomorrow", "1 hour"])
    if line_upper.startswith("DONE|"):
        return ("DONE", [line[5:].strip()])
    if line_upper.startswith("REMOVE|"):
        return ("REMOVE", [line[7:].strip()])
    return None


def _execute_planner(cmd: str, args: list) -> str:
    if cmd == "LIST":
        items = planner.list_assignments(completed=False)
        if not items:
            return "You have no upcoming homework."
        parts = [f"{a['subject']}: {a['assignment']}, due {a['due_date']}" for a in items[:10]]
        return "Your homework: " + ". ".join(parts) if len(parts) == 1 else "You have " + str(len(items)) + " items. " + ". ".join(parts[:3])
    if cmd == "ADD" and len(args) >= 4:
        planner.add_assignment(args[0], args[1], args[2], args[3])
        return f"Added {args[1]} for {args[0]}, due {args[2]}."
    if cmd == "ADD" and len(args) == 1:
        planner.add_assignment("General", args[0], "tomorrow", "1 hour")
        return f"Added {args[0]}."
    if cmd == "DONE" and args:
        a = planner.find_by_name_or_id(args[0])
        if a:
            planner.set_completed(a["id"], True)
            return f"Marked {a['assignment']} as done."
        return "I couldn't find that assignment."
    if cmd == "REMOVE" and args:
        a = planner.find_by_name_or_id(args[0])
        if a:
            planner.delete_assignment(a["id"])
            return f"Removed {a['assignment']}."
        return "I couldn't find that assignment."
    return ""


def _planner_reply(messages: List[dict], user_text: str) -> str:
    full_messages = messages + [{"role": "user", "content": user_text.strip()}]
    raw = _chat(full_messages)
    if not raw:
        return "I didn't get that. Try again."
    lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
    reply_lines = []
    planner_done = None
    for line in lines:
        parsed = _parse_planner_line(line)
        if parsed:
            cmd, args = parsed
            out = _execute_planner(cmd, args)
            if out:
                planner_done = out
        else:
            reply_lines.append(line)
    if planner_done:
        return planner_done
    reply = " ".join(reply_lines).strip()
    if not reply:
        return "Done."
    return _truncate_voice(reply)


def respond(messages: List[dict], user_text: str) -> str:
    if not (user_text or "").strip():
        return ""
    try:
        g = google_router.try_google(user_text.strip())
        if g:
            return g
    except Exception as e:
        logger.warning("Google router: %s", e)
        from features.google import auth as gauth

        return gauth.google_error_message()
    if planner_likely(user_text):
        return _planner_reply(messages, user_text)
    raw = _chat(messages + [{"role": "user", "content": user_text.strip()}])
    if not raw:
        return "I didn't get that. Try again."
    return _truncate_voice(raw)
