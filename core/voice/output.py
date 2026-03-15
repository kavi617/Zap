"""Audio playback – PyAudio or subprocess (avoids ALSA hangs)."""
import logging
import subprocess
import sys
import wave

from core import config

logger = logging.getLogger(__name__)


def _play_via_subprocess(wav_path: str) -> bool:
    """Use aplay/ffplay/paplay/afplay – works when PyAudio/ALSA blocks."""
    candidates = []
    if sys.platform == "linux":
        candidates = ["aplay", "paplay", "ffplay -nodisp -autoexit -loglevel quiet"]
    elif sys.platform == "darwin":
        candidates = ["afplay", "ffplay -nodisp -autoexit -loglevel quiet"]
    elif sys.platform == "win32":
        candidates = ["ffplay -nodisp -autoexit -loglevel quiet"]
    for cmd in candidates:
        parts = cmd.split()
        exe = parts[0]
        args = parts[1:] + [wav_path] if len(parts) > 1 else [wav_path]
        try:
            subprocess.run(
                [exe] + args,
                check=True,
                capture_output=True,
                timeout=60,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return False


def play_wav_file(wav_path: str, chunk_size: int = 1024) -> None:
    if not wav_path:
        return
    method = getattr(config, "PLAYBACK_METHOD", "subprocess")
    if method == "subprocess":
        if _play_via_subprocess(wav_path):
            return
        logger.warning("Subprocess playback failed, trying PyAudio.")
    try:
        import pyaudio
        with wave.open(wav_path, "rb") as wf:
            rate = wf.getframerate()
            width = wf.getsampwidth()
            channels = wf.getnchannels()
            p = pyaudio.PyAudio()
            try:
                stream = p.open(
                    format=p.get_format_from_width(width),
                    channels=channels,
                    rate=rate,
                    output=True,
                    frames_per_buffer=chunk_size,
                )
                data = wf.readframes(chunk_size)
                while data:
                    stream.write(data)
                    data = wf.readframes(chunk_size)
                stream.stop_stream()
                stream.close()
            finally:
                p.terminate()
    except Exception as e:
        logger.warning("Playback failed: %s", e)


def play_wake_sfx(sfx_path: str) -> None:
    """Play wake word SFX (mp3 or wav) fully before returning."""
    if not sfx_path:
        return
    try:
        import pygame
        pygame.mixer.init()
        pygame.mixer.music.load(sfx_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
    except ImportError:
        logger.warning("pygame not installed – install for wake SFX: pip install pygame")
    except Exception as e:
        logger.warning("Wake SFX playback failed: %s", e)
