"""Ollama streaming deltas for low-latency TTS."""
import json
import logging
import re

import requests

from core import config

logger = logging.getLogger(__name__)


def stream_ollama_deltas(messages: list, user_text: str):
    url = f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": [{"role": "system", "content": config.SYSTEM_PROMPT}]
        + messages
        + [{"role": "user", "content": user_text.strip()}],
        "stream": True,
        "options": {"num_predict": getattr(config, "OLLAMA_NUM_PREDICT", 80)},
    }
    try:
        with requests.post(url, json=payload, timeout=config.OLLAMA_TIMEOUT, stream=True) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("done"):
                    break
                msg = data.get("message") or {}
                part = msg.get("content") or ""
                if part:
                    yield part
    except Exception as e:
        logger.exception("Ollama stream failed: %s", e)


def buffer_phrases(deltas):
    """Yield chunks after ~5–10 words or at punctuation (first audio ASAP)."""
    buf = ""
    for d in deltas:
        buf += d
        w = len(buf.split())
        if w < 4 and not re.search(r"[,.!?;:]", buf):
            continue
        if w >= 5 and (re.search(r"[,.!?]\s*$", buf.strip()) or w >= 10):
            chunk = buf.strip()
            if chunk:
                yield chunk
            buf = ""
    if buf.strip():
        yield buf.strip()
