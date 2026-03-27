"""Google Calendar – create, list, update events."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from features.google import auth

logger = logging.getLogger(__name__)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def list_events(time_min: datetime, time_max: datetime) -> List[dict]:
    try:
        svc = auth.calendar_service()
        ev = (
            svc.events()
            .list(
                calendarId="primary",
                timeMin=_iso(time_min),
                timeMax=_iso(time_max),
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
    if end is None:
        end = start + timedelta(hours=1)
    try:
        svc = auth.calendar_service()
        body: dict[str, Any] = {
            "summary": title,
            "description": description,
            "start": {"dateTime": _iso(start), "timeZone": "UTC"},
            "end": {"dateTime": _iso(end), "timeZone": "UTC"},
        }
        created = svc.events().insert(calendarId="primary", body=body).execute()
        return created.get("htmlLink") or ""
    except Exception as e:
        logger.exception("Calendar create failed: %s", e)
        raise


def update_event(event_id: str, title: Optional[str] = None, start: Optional[datetime] = None) -> None:
    try:
        svc = auth.calendar_service()
        ev = svc.events().get(calendarId="primary", eventId=event_id).execute()
        if title:
            ev["summary"] = title
        if start:
            ev["start"] = {"dateTime": _iso(start), "timeZone": "UTC"}
            ev["end"] = {"dateTime": _iso(start + timedelta(hours=1)), "timeZone": "UTC"}
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
        start = it.get("start", {})
        s = start.get("dateTime") or start.get("date", "")
        parts.append(f"{t} at {s}")
    return ". ".join(parts)
