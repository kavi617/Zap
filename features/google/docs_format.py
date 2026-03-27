"""Build Google Docs batchUpdate requests from markdown-like body (##, ###, **bold**)."""
from __future__ import annotations

import re
from typing import Any


def _inline_runs(text: str) -> list[tuple[bool, str]]:
    if not text:
        return []
    parts = re.split(r"(\*\*.+?\*\*)", text)
    out: list[tuple[bool, str]] = []
    for p in parts:
        if not p:
            continue
        if p.startswith("**") and p.endswith("**") and len(p) > 4:
            out.append((True, p[2:-2]))
        else:
            out.append((False, p))
    return out


def build_requests_from_markdown(body: str) -> list[dict[str, Any]]:
    """Insert formatted content starting at index 1 (new empty doc)."""
    body = (body or "").strip()
    if not body:
        return []

    blocks: list[tuple[str, str]] = []
    for para in re.split(r"\n\s*\n+", body):
        para = para.strip()
        if not para:
            continue
        if para.startswith("### "):
            blocks.append(("H2", para[4:].strip()))
        elif para.startswith("## "):
            blocks.append(("H1", para[3:].strip()))
        else:
            blocks.append(("P", para))

    requests: list[dict[str, Any]] = []
    idx = 1

    def insert_text(t: str) -> tuple[int, int]:
        nonlocal idx
        start = idx
        if not t:
            return start, start
        requests.append({"insertText": {"location": {"index": idx}, "text": t}})
        idx += len(t)
        return start, idx

    first = True
    for kind, raw in blocks:
        if not first:
            insert_text("\n")
        first = False

        para_start = idx
        for is_bold, run in _inline_runs(raw):
            if not run:
                continue
            rs, re_ = insert_text(run)
            if is_bold:
                requests.append(
                    {
                        "updateTextStyle": {
                            "range": {"startIndex": rs, "endIndex": re_},
                            "textStyle": {"bold": True},
                            "fields": "bold",
                        }
                    }
                )
        insert_text("\n")
        para_end = idx

        named = "HEADING_1" if kind == "H1" else "HEADING_2" if kind == "H2" else "NORMAL_TEXT"
        requests.append(
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": para_start, "endIndex": para_end},
                    "paragraphStyle": {"namedStyleType": named},
                    "fields": "namedStyleType",
                }
            }
        )

    return requests
