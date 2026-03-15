"""
Zap – 100% voice-operated student assistant. test
Session disabled for now (can re-add later). Focus: fast STT -> LLM -> TTS.
"""
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import config
from core.voice import input as voice_input, stt, llm, tts
from features.planner import init_db as planner_init_db

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format=config.LOG_FORMAT,
)
logger = logging.getLogger(__name__)


def run_once() -> bool:
    """One cycle: record -> STT -> LLM -> TTS (no session for now)."""
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
    messages = []  # Session disabled – pass [] for now
    t2 = time.perf_counter()
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
    logger.info("Zap started. Say Hey Zap, then ask or use planner commands.")
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
        logger.info("Bye.")


if __name__ == "__main__":
    main()
    sys.exit(0)
