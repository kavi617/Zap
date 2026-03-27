"""
Zap – voice student assistant: STT → LLM → TTS, planner, Google (Calendar/Docs/Gmail), warning daemon.
"""
import logging
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests

from core import config
from core import tts_stream
from core import warning_daemon
from core.voice import input as voice_input, stt, llm, tts
from features.planner import init_db as planner_init_db

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format=config.LOG_FORMAT,
)
logger = logging.getLogger(__name__)


def _prewarm_ollama() -> None:
    try:
        requests.get(f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=8)
        logger.info("Ollama reachable.")
    except Exception as e:
        logger.warning("Ollama prewarm: %s", e)


def _prewarm_google_async() -> None:
    def run():
        try:
            from features.google import auth
            from features.google import router as google_router

            if config.GOOGLE_PREWARM:
                auth.prewarm()
                google_router.refresh_cache()
        except Exception as e:
            logger.debug("Google prewarm: %s", e)

    threading.Thread(target=run, name="google_prewarm", daemon=True).start()


def run_once() -> bool:
    raw = voice_input.record_audio()
    if not raw:
        logger.info("No speech. Try again.")
        return False
    t0 = time.perf_counter()
    user_text = stt.transcribe(raw)
    t1 = time.perf_counter()
    logger.info("[%s] Whisper: %.2fs", time.strftime("%H:%M:%S", time.localtime()), t1 - t0)
    if not user_text:
        logger.info("Could not transcribe.")
        return False
    logger.info("You: %s", user_text)
    messages = []
    t2 = time.perf_counter()
    if getattr(config, "USE_STREAMING_TTS", False):
        n = 0
        t_first = None
        t4 = time.perf_counter()
        for ch in llm.voice_reply_chunks(messages, user_text):
            if t_first is None:
                t_first = time.perf_counter()
                logger.info(
                    "[%s] LLM first chunk: %.2fs",
                    time.strftime("%H:%M:%S", time.localtime()),
                    t_first - t2,
                )
            n += 1
            tts_stream.speak_streaming(ch)
        t5 = time.perf_counter()
        logger.info(
            "[%s] LLM+TTS streaming (%s chunks): %.2fs",
            time.strftime("%H:%M:%S", time.localtime()),
            n,
            t5 - t4,
        )
    else:
        reply = llm.respond(messages, user_text)
        t3 = time.perf_counter()
        logger.info("[%s] LLM: %.2fs", time.strftime("%H:%M:%S", time.localtime()), t3 - t2)
        if reply:
            t4 = time.perf_counter()
            tts.speak(reply)
            t5 = time.perf_counter()
            logger.info("[%s] Piper: %.2fs", time.strftime("%H:%M:%S", time.localtime()), t5 - t4)
    return True


def main():
    planner_init_db()
    _prewarm_ollama()
    tts_stream.prewarm()
    _prewarm_google_async()
    if getattr(config, "WARNING_DAEMON_ENABLED", True):
        warning_daemon.start()
    logger.info("Zap started. Say Hey Zap, then ask or use planner / Google commands.")
    try:
        while True:
            try:
                if not voice_input.wait_for_wake_word():
                    break
                run_once()
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.exception("Error: %s", e)
    finally:
        warning_daemon.stop()
        logger.info("Bye.")


if __name__ == "__main__":
    main()
    sys.exit(0)
