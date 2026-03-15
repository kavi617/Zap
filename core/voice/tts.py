"""Text-to-speech via Piper."""
import logging
import os
import tempfile
from pathlib import Path

from core import config

logger = logging.getLogger(__name__)
_voice = None


def _load_voice():
    global _voice
    if _voice is not None:
        return _voice
    from piper import PiperVoice
    voice = config.PIPER_VOICE
    if not voice.endswith(".onnx"):
        voice = f"{voice}.onnx"
    path = Path(config.PIPER_MODEL_DIR) / voice
    if not path.exists():
        path = config.ROOT_DIR / "piper_models" / voice
    if not path.exists():
        raise FileNotFoundError(f"Piper voice not found: {path}. Run: python -m piper.download_voices en_US-lessac-medium")
    _voice = PiperVoice.load(str(path))
    return _voice


def text_to_wav(text: str) -> str:
    if not (text or "").strip():
        return ""
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        import wave
        with wave.open(path, "wb") as wf:
            _load_voice().synthesize_wav(text.strip(), wf)
        return path
    except Exception:
        if os.path.isfile(path):
            os.remove(path)
        raise


def speak(text: str) -> None:
    if not (text or "").strip():
        return
    path = text_to_wav(text)
    if path:
        try:
            from core.voice import output
            output.play_wav_file(path)
        finally:
            if os.path.isfile(path):
                os.remove(path)
