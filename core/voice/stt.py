"""Speech-to-text via Whisper (or faster-whisper for speed)."""
import logging
import numpy as np

from core import config

logger = logging.getLogger(__name__)
_model = None


def _get_model():
    global _model
    if _model is not None:
        return _model
    if getattr(config, "USE_FASTER_WHISPER", False):
        try:
            from faster_whisper import WhisperModel
            logger.info("Loading faster-whisper %s (faster)...", config.WHISPER_MODEL)
            ct = "int8" if config.WHISPER_DEVICE == "cuda" else "float32"
            _model = ("faster", WhisperModel(config.WHISPER_MODEL, device=config.WHISPER_DEVICE, compute_type=ct))
            return _model
        except ImportError:
            logger.warning("faster-whisper not installed. pip install faster-whisper. Using openai-whisper.")
        except Exception as e:
            logger.warning("faster-whisper init failed: %s. Using openai-whisper.", e)
    import whisper
    logger.info("Loading Whisper %s...", config.WHISPER_MODEL)
    _model = ("stock", whisper.load_model(config.WHISPER_MODEL, device=config.WHISPER_DEVICE))
    return _model


def transcribe(audio_bytes: bytes) -> str:
    if not audio_bytes:
        return ""
    audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
    audio_float = audio_int16.astype(np.float32) / 32768.0
    model_type, model = _get_model()
    if model_type == "faster":
        segments, _ = model.transcribe(
            audio_float,
            language=config.WHISPER_LANGUAGE,
            beam_size=1,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=300),
        )
        return " ".join(s.text for s in segments).strip() if segments else ""
    result = model.transcribe(
        audio_float,
        language=config.WHISPER_LANGUAGE,
        fp16=(config.WHISPER_DEVICE == "cuda"),
        best_of=1,
        compression_ratio_threshold=2.4,
        log_prob_threshold=-1.0,
        no_speech_threshold=0.6,
    )
    return (result.get("text") or "").strip()
