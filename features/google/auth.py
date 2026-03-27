"""
Google OAuth – credentials.json + token.json in /core.
Caches credentials for the session; retry once on transient failures.
"""
import logging
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

from core import config

logger = logging.getLogger(__name__)

ROOT = config.ROOT_DIR
CREDENTIALS_PATH = ROOT / "core" / "credentials.json"
TOKEN_PATH = ROOT / "core" / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/gmail.readonly",
]

_creds = None
_services: dict[str, Any] = {}

T = TypeVar("T")


def _retry(fn: Callable[[], T]) -> T:
    try:
        return fn()
    except Exception as e:
        logger.warning("Google API retry: %s", e)
        return fn()


def get_credentials():
    """Load or refresh OAuth credentials; persist to token.json."""
    global _creds
    if _creds is not None and _creds.valid:
        return _creds
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except Exception as e:
            logger.warning("Could not load token.json: %s", e)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(f"Missing {CREDENTIALS_PATH}")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0, open_browser=True)
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    _creds = creds
    return creds


def calendar_service():
    if "calendar" not in _services:
        from googleapiclient.discovery import build

        def _build():
            return build("calendar", "v3", credentials=get_credentials(), cache_discovery=False)

        _services["calendar"] = _retry(_build)
    return _services["calendar"]


def docs_service():
    if "docs" not in _services:
        from googleapiclient.discovery import build

        def _build():
            return build("docs", "v1", credentials=get_credentials(), cache_discovery=False)

        _services["docs"] = _retry(_build)
    return _services["docs"]


def gmail_service():
    if "gmail" not in _services:
        from googleapiclient.discovery import build

        def _build():
            return build("gmail", "v1", credentials=get_credentials(), cache_discovery=False)

        _services["gmail"] = _retry(_build)
    return _services["gmail"]


def prewarm() -> None:
    """Load token and build services once at startup."""
    try:
        get_credentials()
        calendar_service()
        docs_service()
        gmail_service()
        logger.info("Google APIs prewarmed.")
    except Exception as e:
        logger.warning("Google prewarm skipped: %s", e)


def google_error_message() -> str:
    return "I am having trouble connecting to Google right now."
