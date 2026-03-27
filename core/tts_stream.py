"""
Streaming TTS: queue-based playback (Kokoro optional, Piper fallback).
Chunks split at punctuation; synth in background thread while playing.
"""
import logging
import queue
import re
import threading
import tempfile
import os

from core import config

logger = logging.getLogger(__name__)

_prewarmed = False
_kokoro_pipeline = None


def prewarm() -> None:
    global _prewarmed, _kokoro_pipeline
    if _prewarmed:
        return
    try:
        from core.voice import tts as piper_tts
        piper_tts.prewarm()
    except Exception as e:
        logger.warning("Piper prewarm: %s", e)
    _prewarmed = True
    logger.info("TTS pipeline prewarmed.")


def _split_chunks(text: str, max_words: int = 12) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+|(?<=,)\s+|(?<=\s)\band\s+", text, flags=re.I)
    chunks = []
    buf = []
    wcount = 0
    for p in parts:
        p = p.strip()
        if not p:
            continue
        words = len(p.split())
        if buf and wcount + words > max_words and "," not in p and "." not in p:
            chunks.append(" ".join(buf).strip())
            buf = []
            wcount = 0
        buf.append(p)
        wcount += words
        if wcount >= 5 and ("," in p or "." in p or "!" in p or "?" in p):
            chunks.append(" ".join(buf).strip())
            buf = []
            wcount = 0
    if buf:
        chunks.append(" ".join(buf).strip())
    return [c for c in chunks if c]


def _synth_chunk(text: str) -> str | None:
    try:
        from core.voice import tts as piper_tts
        return piper_tts.text_to_wav(text)
    except Exception as e:
        logger.warning("Chunk synth failed: %s", e)
        return None


def speak_streaming(full_text: str) -> None:
    """Synthesize and play in overlapping pipeline (queue + threads)."""
    chunks = _split_chunks(full_text)
    if not chunks:
        return
    from core.voice import output

    q: queue.Queue[str | None] = queue.Queue(maxsize=4)
    done = threading.Event()

    def producer():
        for ch in chunks:
            path = _synth_chunk(ch)
            if path:
                q.put(path)
        q.put(None)

    def consumer():
        while True:
            item = q.get()
            if item is None:
                break
            try:
                output.play_wav_file(item)
            finally:
                if os.path.isfile(item):
                    try:
                        os.remove(item)
                    except OSError:
                        pass
            q.task_done()

    t1 = threading.Thread(target=producer, daemon=True)
    t2 = threading.Thread(target=consumer, daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()


def speak_simple(text: str) -> None:
    """Non-streaming short reply."""
    from core.voice import tts
    tts.speak(text)
