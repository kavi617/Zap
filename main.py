"""
Zap – voice assistant: wake → STT → LLM → Piper TTS, planner, Google, warning daemon.
"""
import logging
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import console_ui

console_ui.install_stderr_filter()

import requests

from core import config
from core import warning_daemon
from core.voice import input as voice_input, stt, llm, tts
from features.planner import init_db as planner_init_db

logging.basicConfig(
    level=logging.WARNING,
    format=config.LOG_FORMAT,
)
logger = logging.getLogger(__name__)


def _prewarm_ollama() -> bool:
    try:
        requests.get(f"{config.OLLAMA_BASE_URL.rstrip('/')}/api/tags", timeout=8)
        return True
    except Exception:
        return False


def _prewarm_google_async() -> None:
    """Calendar cache without blocking OAuth (auth prewarmed in main)."""

    def run():
        try:
            from features.google import router as google_router

            if config.GOOGLE_PREWARM:
                google_router.refresh_cache()
        except Exception:
            pass

    threading.Thread(target=run, name="google_prewarm", daemon=True).start()


def run_once() -> bool:
    raw = voice_input.record_audio()
    if not raw:
        console_ui.system_processing("No speech detected — try again.")
        return False
    t0 = time.perf_counter()
    user_text = stt.transcribe(raw)
    t1 = time.perf_counter()
    stt_dt = t1 - t0
    if stt_dt >= 1.0:
        console_ui.stt_line(stt_dt)
    else:
        console_ui.stt_line(0.5)

    if not user_text:
        console_ui.system_processing("Could not transcribe.")
        return False
    console_ui.you_spoke(user_text)

    messages = []
    t2 = time.perf_counter()

    try:
        reply = llm.respond(messages, user_text)
        t3 = time.perf_counter()
        if t3 - t2 >= 1.0:
            console_ui.system_processing(f"LLM ({t3 - t2:.1f}s)")
        if reply:
            console_ui.zap_reply_preview(reply)
            t4 = time.perf_counter()
            tts.speak(reply)
            t5 = time.perf_counter()
            if t5 - t4 >= 1.0:
                console_ui.system_processing(f"TTS ({t5 - t4:.1f}s)")
    except Exception as e:
        console_ui.error_line(str(e)[:120])
        logger.exception("Pipeline error")
        try:
            from features.google import auth as gauth

            tts.speak(gauth.google_error_message())
        except Exception:
            pass
        return False

    console_ui.divider()
    console_ui.system_ready()
    return True


def main():
    console_ui.clear_screen()
    console_ui.banner()

    planner_init_db()

    if _prewarm_ollama():
        console_ui.system_ok("Ollama connected")
    else:
        console_ui.error_line("Ollama not reachable — check OLLAMA_BASE_URL")

    tts.prewarm()
    console_ui.system_ok("TTS ready")

    try:
        from features.google import auth as gauth

        gauth.prewarm()
        console_ui.system_ok("Google APIs connected")
    except Exception:
        console_ui.system_processing(
            "Google APIs not ready — add core/credentials.json and sign in once",
        )

    _prewarm_google_async()

    if getattr(config, "WARNING_DAEMON_ENABLED", True):
        warning_daemon.start()
        console_ui.system_ok("Warning daemon running")

    console_ui.system_ok('Listening for "Hey Zap"...')
    console_ui.divider()

    try:
        while True:
            try:
                if not voice_input.wait_for_wake_word():
                    break
                console_ui.wake()
                run_once()
            except KeyboardInterrupt:
                break
            except Exception as e:
                console_ui.error_line(str(e)[:120])
                logger.exception("Loop error")
    finally:
        warning_daemon.stop()
        console_ui.system_processing("Goodbye.")


if __name__ == "__main__":
    main()
    sys.exit(0)
