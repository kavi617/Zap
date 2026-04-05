"""Google Docs – create and update documents with optional rich formatting."""
import logging
import webbrowser
from typing import Optional

from features.google import auth
from features.google.docs_format import build_requests_from_markdown

logger = logging.getLogger(__name__)

# Google Docs API: max 50 requests per batchUpdate; exceed → error or partial apply
_DOCS_BATCH_SIZE = 50

_last_doc_id: Optional[str] = None
_last_doc_title: str = ""


def get_recent_doc_id() -> Optional[str]:
    return _last_doc_id


def create_document_rich(title: str, markdown_body: str) -> tuple[str, str]:
    """
    Create a new Google Doc with HEADING_1/HEADING_2 and bold from markdown_body.
    Title is document title only (clean, no sentences).
    """
    global _last_doc_id, _last_doc_title
    try:
        svc = auth.docs_service()
        created = svc.documents().create(body={"title": title.strip()}).execute()
        doc_id = created.get("documentId")
        if not doc_id:
            raise RuntimeError("No documentId from create")
        reqs = build_requests_from_markdown(markdown_body)
        if reqs:
            for start in range(0, len(reqs), _DOCS_BATCH_SIZE):
                chunk = reqs[start : start + _DOCS_BATCH_SIZE]
                svc.documents().batchUpdate(documentId=doc_id, body={"requests": chunk}).execute()
        link = f"https://docs.google.com/document/d/{doc_id}/edit"
        _last_doc_id = doc_id
        _last_doc_title = title.strip()
        return doc_id, link
    except Exception as e:
        logger.exception("Docs create failed: %s", e)
        raise


def update_document_body(doc_id: str, new_text: str, replace_all: bool = False) -> None:
    try:
        svc = auth.docs_service()
        doc = svc.documents().get(documentId=doc_id).execute()
        end_index = doc.get("body", {}).get("content", [{}])[-1].get("endIndex", 2)
        end_index = max(1, int(end_index) - 1)
        if replace_all:
            body = _read_plain_text(doc)
            if body:
                requests = [{"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end_index + 1}}}]
                svc.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
                doc = svc.documents().get(documentId=doc_id).execute()
                end_index = doc.get("body", {}).get("content", [{}])[-1].get("endIndex", 2)
                end_index = max(1, int(end_index) - 1)
        requests = [{"insertText": {"location": {"index": end_index - 1}, "text": new_text}}]
        svc.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
    except Exception as e:
        logger.exception("Docs update failed: %s", e)
        raise


def _read_plain_text(doc: dict) -> str:
    parts = []
    for el in doc.get("body", {}).get("content", []):
        if "paragraph" in el:
            for el2 in el["paragraph"].get("elements", []):
                tr = el2.get("textRun")
                if tr and "content" in tr:
                    parts.append(tr["content"])
    return "".join(parts)


def open_in_browser(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception as e:
        logger.warning("Could not open browser: %s", e)
