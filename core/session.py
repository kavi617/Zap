"""
Session memory – conversation history for context-aware follow-ups.
Initialized at startup; cleared when process exits.
"""
from typing import List

_messages: List[dict] = []


def init_session() -> None:
    _messages.clear()


def get_messages() -> List[dict]:
    return list(_messages)


def append_turn(role: str, content: str) -> None:
    if content and role in ("user", "assistant"):
        _messages.append({"role": role, "content": content.strip()})


def clear_session() -> None:
    _messages.clear()
