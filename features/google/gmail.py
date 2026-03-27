"""Gmail – readonly; fetch unread for summarization."""
import logging
import base64
from typing import List

from features.google import auth

logger = logging.getLogger(__name__)


def _decode_body(payload: dict) -> str:
    data = payload.get("body", {}).get("data")
    if data:
        try:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        except Exception:
            return ""
    for part in payload.get("parts", []) or []:
        if part.get("mimeType") == "text/plain":
            return _decode_body(part)
    return ""


def list_unread(limit: int = 10) -> List[dict]:
    try:
        svc = auth.gmail_service()
        r = (
            svc.users()
            .messages()
            .list(userId="me", labelIds=["INBOX", "UNREAD"], maxResults=limit)
            .execute()
        )
        msgs = r.get("messages") or []
        out = []
        for m in msgs[:limit]:
            mid = m["id"]
            full = svc.users().messages().get(userId="me", id=mid, format="full").execute()
            headers = {h["name"].lower(): h["value"] for h in full.get("payload", {}).get("headers", [])}
            subj = headers.get("subject", "(no subject)")
            frm = headers.get("from", "")
            snippet = full.get("snippet", "")
            body = _decode_body(full.get("payload", {}))[:2000]
            out.append({
                "id": mid,
                "from": frm,
                "subject": subj,
                "snippet": snippet,
                "body_preview": body or snippet,
            })
        return out
    except Exception as e:
        logger.exception("Gmail list failed: %s", e)
        raise
