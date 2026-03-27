"""Voice input: wake word + VAD recording (fast end-of-speech)."""
import logging
import struct
import threading
from pathlib import Path

import pyaudio

from core import config

logger = logging.getLogger(__name__)
FORMAT = pyaudio.paInt16


def _is_silence(chunk: bytes, threshold: float) -> bool:
    if not chunk:
        return True
    count = len(chunk) // 2
    if count == 0:
        return True
    samples = struct.unpack_from(f"{count}h", chunk)
    rms = (sum(s * s for s in samples) / count) ** 0.5
    return (rms / 32768.0) < threshold


def _play_wake_sfx() -> None:
    path = getattr(config, "WAKE_SFX_PATH", "") or ""
    if not path:
        return
    from core.voice import output
    output.play_wake_sfx(path)


def record_audio() -> bytes:
    """Record until ~SILENCE_END_MS after speech ends (energy VAD). No fixed window."""
    p = pyaudio.PyAudio()
    try:
        stream = p.open(
            format=FORMAT,
            channels=config.CHANNELS,
            rate=config.SAMPLE_RATE,
            input=True,
            frames_per_buffer=config.CHUNK_SIZE,
        )
    except Exception as e:
        logger.error("Failed to open microphone: %s", e)
        raise
    try:
        silence_ms = getattr(config, "SILENCE_END_MS", 300)
        silence_limit = max(
            1,
            int(silence_ms / 1000.0 * config.SAMPLE_RATE / config.CHUNK_SIZE),
        )
        min_chunks = int(config.MIN_SPEECH_LENGTH * config.SAMPLE_RATE / config.CHUNK_SIZE)
        max_chunks = int(config.RECORD_SECONDS * config.SAMPLE_RATE / config.CHUNK_SIZE)
        frames = []
        silent_chunks = 0
        speech_started = False
        for _ in range(max_chunks):
            chunk = stream.read(config.CHUNK_SIZE, exception_on_overflow=False)
            frames.append(chunk)
            if _is_silence(chunk, config.SILENCE_THRESHOLD):
                if speech_started:
                    silent_chunks += 1
                    if silent_chunks >= silence_limit:
                        break
            else:
                speech_started = True
                silent_chunks = 0
        if not speech_started or len(frames) < min_chunks:
            return b""
        return b"".join(frames)
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()


def wait_for_wake_word() -> bool:
    """Wake word detected → SFX in background; return immediately so STT can start in parallel."""
    if not config.WAKE_WORD_ENABLED:
        return True
    try:
        import pvporcupine
    except ImportError as e:
        logger.warning("Wake word deps missing: %s. Say something to continue.", e)
        return True
    if not config.PORCUPINE_ACCESS_KEY:
        logger.warning("PORCUPINE_ACCESS_KEY not set. Say something to continue.")
        return True
    paths = [p for p in config.WAKE_WORD_KEYWORD_PATHS if Path(p).exists()]
    try:
        if paths:
            porcupine = pvporcupine.create(
                access_key=config.PORCUPINE_ACCESS_KEY,
                keyword_paths=paths,
                sensitivities=[config.WAKE_WORD_SENSITIVITY] * len(paths),
            )
        else:
            porcupine = pvporcupine.create(
                access_key=config.PORCUPINE_ACCESS_KEY,
                keywords=[config.WAKE_WORD_BUILTIN],
                sensitivities=[config.WAKE_WORD_SENSITIVITY],
            )
    except Exception as e:
        logger.warning("Porcupine init failed: %s", e)
        return True
    p = pyaudio.PyAudio()
    stream = p.open(
        rate=porcupine.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=porcupine.frame_length,
    )
    try:
        while True:
            chunk = stream.read(porcupine.frame_length, exception_on_overflow=False)
            frame = struct.unpack_from("h" * porcupine.frame_length, chunk)
            if porcupine.process(list(frame)) >= 0:
                threading.Thread(target=_play_wake_sfx, name="wake_sfx", daemon=True).start()
                return True
    except KeyboardInterrupt:
        return False
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        porcupine.delete()
