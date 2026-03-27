"""
Streaming TTS: producer/consumer queues — synth runs ahead of playback for gapless audio.
LLM yields text chunks independently; never blocks the LLM thread on playback.
"""
import logging
import os
import queue
import re
import threading

logger = logging.getLogger(__name__)

_prewarmed = False


def prewarm() -> None:
    global _prewarmed
    if _prewarmed:
        return
    try:
        from core.voice import tts as piper_tts
        piper_tts.prewarm()
    except Exception as e:
        logger.warning("Piper prewarm: %s", e)
    _prewarmed = True
    logger.info("TTS pipeline prewarmed.")


def _split_chunks(text: str, max_words: int = 14) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+|(?<=,)\s+|(?<=\s)\band\s+|(?<=\s)\bbut\s+", text, flags=re.I)
    chunks = []
    buf: list[str] = []
    wcount = 0
    for p in parts:
        p = p.strip()
        if not p:
            continue
        words = len(p.split())
        if buf and wcount + words > max_words and not re.search(r"[,.!?]", p):
            chunks.append(" ".join(buf).strip())
            buf = []
            wcount = 0
        buf.append(p)
        wcount += words
        if wcount >= 4 and (re.search(r"[,.!?]\s*$", p) or wcount >= max_words):
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
    """Backward compat: one reply split into chunks with pipeline."""
    speak_streaming_pipeline(iter(_split_chunks(full_text)))


def speak_streaming_pipeline(text_chunk_iterator):
    """
    Continuous audio from an iterator of text strings (e.g. LLM phrase chunks).
    Text queue → synth → wav queue → playback; synth stays ahead of playback.
    """
    text_q: queue.Queue[str | None] = queue.Queue(maxsize=32)
    wav_q: queue.Queue[str | None] = queue.Queue(maxsize=8)

    def feed_text():
        try:
            for ch in text_chunk_iterator:
                if not ch:
                    continue
                for sub in _split_chunks(ch):
                    text_q.put(sub)
        finally:
            text_q.put(None)

    def synth_worker():
        while True:
            txt = text_q.get()
            if txt is None:
                wav_q.put(None)
                return
            path = _synth_chunk(txt)
            if path:
                wav_q.put(path)

    def play_worker():
        from core.voice import output
        while True:
            path = wav_q.get()
            if path is None:
                return
            try:
                output.play_wav_file(path)
            finally:
                if os.path.isfile(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

    t_feed = threading.Thread(target=feed_text, name="tts_feed", daemon=True)
    t_syn = threading.Thread(target=synth_worker, name="tts_synth", daemon=True)
    t_play = threading.Thread(target=play_worker, name="tts_play", daemon=True)
    t_feed.start()
    t_syn.start()
    t_play.start()
    t_feed.join()
    t_syn.join()
    t_play.join()


def speak_simple(text: str) -> None:
    from core.voice import tts
    tts.speak(text)
