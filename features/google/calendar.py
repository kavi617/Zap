"""Google Calendar – create, list, update events; voice-friendly time strings for TTS."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from features.google import auth

logger = logging.getLogger(__name__)

# Spoken hour words (1–12) for natural TTS
_HOUR_WORDS = (
    None,
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
)


def _effective_tz_name() -> str:
    from core import config

    t = getattr(config, "LOCAL_TIMEZONE", "").strip()
    if t:
        return t
    try:
        from tzlocal import get_localzone_name

        return get_localzone_name() or "UTC"
    except Exception:
        return "UTC"


def _iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _dt_for_voice(dt: datetime) -> str:
    """Natural phrase for Piper — no ISO, no second/microsecond noise."""
    zi = None
    try:
        from zoneinfo import ZoneInfo

        zi = ZoneInfo(_effective_tz_name())
    except Exception:
        pass
    local = dt.astimezone(zi) if zi else dt.astimezone()
    weekday = local.strftime("%A")
    month = local.strftime("%B")
    day = int(local.day)
    if 11 <= day <= 13:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    h12 = local.hour % 12 or 12
    hw = _HOUR_WORDS[h12] or str(h12)
    is_am = local.hour < 12
    mer = "AM" if is_am else "PM"
    minute = local.minute
    if minute == 0:
        time_part = f"{hw} {mer}"
    elif minute == 30:
        time_part = f"{hw} thirty {mer}"
    elif minute == 15:
        time_part = f"{hw} fifteen {mer}"
    elif minute == 45:
        time_part = f"{hw} forty-five {mer}"
    else:
        time_part = f"{hw} {minute} {mer}"
    return f"{weekday}, {month} {day}{suf} at {time_part}"


def format_instant_for_voice(dt_utc: datetime) -> str:
    """Public: format a UTC (or aware) datetime for spoken confirmation."""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return _dt_for_voice(dt_utc)


def _parse_event_iso(ev: dict) -> datetime | None:
    start = ev.get("start") or {}
    if start.get("date") and not start.get("dateTime"):
        return None
    s = start.get("dateTime") or start.get("date", "")
    if not s:
        return None
    try:
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        return datetime.fromisoformat(f"{s}T00:00:00+00:00")
    except Exception:
        return None


def format_event_time_for_voice(ev: dict) -> str:
    """Turn API dateTime (often long ISO) into a short human line for TTS."""
    start = ev.get("start") or {}
    if start.get("date") and not start.get("dateTime"):
        return "all day"
    dt = _parse_event_iso(ev)
    if dt is None:
        return (start.get("dateTime") or start.get("date") or "")[:40]
    return _dt_for_voice(dt)


def list_events(time_min: datetime, time_max: datetime) -> List[dict]:
    try:
        svc = auth.calendar_service()
        ev = (
            svc.events()
            .list(
                calendarId="primary",
                timeMin=_iso_utc(time_min),
                timeMax=_iso_utc(time_max),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return ev.get("items") or []
    except Exception as e:
        logger.exception("Calendar list failed: %s", e)
        raise


def events_due_within_hours(hours: float = 1.0) -> List[dict]:
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=hours)
    items = list_events(now, end)
    out = []
    for it in items:
        start = it.get("start", {})
        s = start.get("dateTime") or start.get("date")
        if not s:
            continue
        try:
            if "T" in s:
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(s + "T00:00:00+00:00")
        except Exception:
            continue
        if now <= dt <= end:
            out.append(it)
    return out


def create_event(title: str, start: datetime, end: Optional[datetime] = None, description: str = "") -> str:
    """Create event using calendar timeZone + local wall time (matches Google Calendar app)."""
    if end is None:
        end = start + timedelta(hours=1)
    tz_name = _effective_tz_name()
    try:
        from zoneinfo import ZoneInfo

        zi = ZoneInfo(tz_name)
    except Exception:
        zi = timezone.utc
        tz_name = "UTC"

    su = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
    eu = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
    su = su.astimezone(zi)
    eu = eu.astimezone(zi)

    def _fmt_wall(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%dT%H:%M:%S")

    try:
        svc = auth.calendar_service()
        body: dict[str, Any] = {
            "summary": title,
            "description": description,
            "start": {"dateTime": _fmt_wall(su), "timeZone": tz_name},
            "end": {"dateTime": _fmt_wall(eu), "timeZone": tz_name},
        }
        created = svc.events().insert(calendarId="primary", body=body).execute()
        return created.get("htmlLink") or ""
    except Exception as e:
        logger.exception("Calendar create failed: %s", e)
        raise


def update_event(event_id: str, title: Optional[str] = None, start: Optional[datetime] = None) -> None:
    tz_name = _effective_tz_name()
    try:
        from zoneinfo import ZoneInfo

        zi = ZoneInfo(tz_name)
    except Exception:
        zi = timezone.utc
        tz_name = "UTC"

    try:
        svc = auth.calendar_service()
        ev = svc.events().get(calendarId="primary", eventId=event_id).execute()
        if title:
            ev["summary"] = title
        if start:
            su = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
            su = su.astimezone(zi)
            end_raw = start + timedelta(hours=1)
            if end_raw.tzinfo is None:
                end_raw = end_raw.replace(tzinfo=timezone.utc)
            eu = end_raw.astimezone(zi)
            ev["start"] = {"dateTime": su.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": tz_name}
            ev["end"] = {"dateTime": eu.strftime("%Y-%m-%dT%H:%M:%S"), "timeZone": tz_name}
        svc.events().update(calendarId="primary", eventId=event_id, body=ev).execute()
    except Exception as e:
        logger.exception("Calendar update failed: %s", e)
        raise


def format_events_for_voice(items: List[dict], max_items: int = 5) -> str:
    if not items:
        return "Nothing on your calendar in that range."
    parts = []
    for it in items[:max_items]:
        t = it.get("summary", "Event")
        when = format_event_time_for_voice(it)
        parts.append(f"{t}, {when}")
    return ". ".join(parts)


def format_events_conversational(items: List[dict], intro: str) -> str:
    if not items:
        return f"{intro} You have nothing scheduled."
    bits = []
    for it in items[:8]:
        t = it.get("summary", "Event")
        when = format_event_time_for_voice(it)
        bits.append(f"{t} — {when}")
    return f"{intro} " + "; ".join(bits) + "."


def list_tomorrow_events() -> List[dict]:
    """Tomorrow in the user's local timezone (not UTC midnight)."""
    try:
        from zoneinfo import ZoneInfo

        zi = ZoneInfo(_effective_tz_name())
    except Exception:
        zi = timezone.utc
    now = datetime.now(zi)
    tomorrow = now.date() + timedelta(days=1)
    day_start = datetime(
        tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0, tzinfo=zi
    )
    day_end = day_start + timedelta(days=1)
    return list_events(day_start.astimezone(timezone.utc), day_end.astimezone(timezone.utc))


def find_upcoming_events_matching(keyword: str, days: int = 14) -> List[dict]:
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    items = list_events(now, end)
    kw = (keyword or "").lower().strip()
    if not kw:
        return []
    return [e for e in items if kw in (e.get("summary") or "").lower()]
