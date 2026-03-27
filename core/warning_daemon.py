"""
Background thread: every 5 minutes check calendar + planner for due-within-1-hour.
Play warning.mp3 (placeholder path) then voice announcement.
"""
import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core import config

logger = logging.getLogger(__name__)

_warned_path = config.DATA_DIR / "warning_warned.json"
_stop = threading.Event()
_thread: threading.Thread | None = None


def _load_warned() -> set[str]:
    if not _warned_path.exists():
        return set()
    try:
        data = json.loads(_warned_path.read_text(encoding="utf-8"))
        return set(data) if isinstance(data, list) else set()
    except Exception:
        return set()


def _save_warned(s: set[str]) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    _warned_path.write_text(json.dumps(list(s)), encoding="utf-8")


def _warning_sfx_path() -> str:
    for rel in ["assets/warning.mp3", "core/warning.mp3"]:
        p = config.ROOT_DIR / rel
        if p.exists():
            return str(p)
    return ""


def _play_warning_sfx() -> None:
    path = _warning_sfx_path()
    if not path:
        logger.debug("warning.mp3 not found (placeholder); add assets/warning.mp3")
        return
    from core.voice import output
    output.play_wake_sfx(path)


def _announce(text: str) -> None:
    try:
        from core.voice import tts
        tts.speak(text)
    except Exception as e:
        logger.warning("Warning announce failed: %s", e)


def _check_once(warned: set[str]) -> set[str]:
    alerts = []
    try:
        from features.google import auth, calendar
        from features import planner

        auth.get_credentials()
        for ev in calendar.events_due_within_hours(1.0):
            eid = ev.get("id") or ""
            key = f"cal:{eid}"
            if eid and key not in warned:
                t = ev.get("summary", "Event")
                alerts.append((key, f"Heads up. On your calendar soon: {t}."))
    except Exception as e:
        logger.debug("Calendar warning check: %s", e)

    try:
        from features import planner

        now = datetime.now(timezone.utc)
        end = now + timedelta(hours=1)
        for a in planner.list_assignments(completed=False):
            due_raw = (a.get("due_date") or "").strip()
            if not due_raw:
                continue
            try:
                import dateparser

                dt = dateparser.parse(due_raw, settings={"RETURN_AS_TIMEZONE_AWARE": True})
            except Exception:
                dt = None
            if dt is None:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if not (now <= dt <= end):
                continue
            key = f"planner:{a.get('id')}"
            if key in warned:
                continue
            subj = a.get("subject", "Homework")
            asn = a.get("assignment", "")
            alerts.append((key, f"Reminder. {subj}: {asn} is due within the hour."))
    except Exception as e:
        logger.debug("Planner warning check: %s", e)

    for key, msg in alerts:
        _play_warning_sfx()
        _announce(msg)
        warned.add(key)
    return warned


def _loop() -> None:
    warned = _load_warned()
    while not _stop.is_set():
        try:
            warned = _check_once(warned)
            _save_warned(warned)
        except Exception as e:
            logger.exception("Warning daemon tick: %s", e)
        for _ in range(300):
            if _stop.is_set():
                break
            time.sleep(1)


def start() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="warning_daemon", daemon=True)
    _thread.start()
    logger.info("Warning daemon started (5 min interval).")


def stop() -> None:
    _stop.set()
    if _thread:
        _thread.join(timeout=2.0)
