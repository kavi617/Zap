"""
Zap – single config. Voice-only assistant. Edit here or via .env.
"""
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
PLANNER_DB_PATH = DATA_DIR / "planner.db"

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")
    if (Path.cwd() / ".env").exists():
        load_dotenv(Path.cwd() / ".env")
except ImportError:
    pass

def _env(key: str, default: str) -> str:
    return os.environ.get(key, default).strip()
def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except ValueError:
        return default
def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, str(default)))
    except ValueError:
        return default
def _env_bool(key: str, default: bool) -> bool:
    v = os.environ.get(key, "").strip().lower()
    return v in ("1", "true", "yes") if v else default

# Ollama — short answers for sub‑5s voice turns (use a small fast model, e.g. qwen2:0.5b)
OLLAMA_BASE_URL = _env("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = _env("OLLAMA_MODEL", "qwen2:0.5b")
OLLAMA_TIMEOUT = _env_int("OLLAMA_TIMEOUT", 8)
# Long Google Doc / Gmail summarization — allow enough time for local Ollama to finish
OLLAMA_TIMEOUT_GOOGLE = _env_int("OLLAMA_TIMEOUT_GOOGLE", 180)
OLLAMA_NUM_PREDICT = _env_int("OLLAMA_NUM_PREDICT", 64)
# Full essay/report bodies need a high token cap (384 was cutting output mid‑paragraph)
OLLAMA_NUM_PREDICT_GOOGLE = _env_int("OLLAMA_NUM_PREDICT_GOOGLE", 4096)
OLLAMA_NUM_PREDICT_ROUTER = _env_int("OLLAMA_NUM_PREDICT_ROUTER", 160)
VOICE_REPLY_MAX_CHARS = _env_int("VOICE_REPLY_MAX_CHARS", 220)

# Tutor + planner — one or two short sentences, plain words, voice-first
SYSTEM_PROMPT = _env(
    "SYSTEM_PROMPT",
    """You are Zap, a voice-only student helper. Reply in at most two short sentences. Use simple words a kid can hear once and understand.
No bullet points, no lists, no "first/second/third". No long explanations unless the user clearly asks for detail.
Homework planner: when they want to add/list/done/remove homework, say one brief line, then on a NEW LINE exactly one of:
ADD|subject|assignment name|due date and time|estimated time
LIST
DONE|assignment name or number
REMOVE|assignment name or number
Otherwise just answer the question in plain speech. No ADD/LIST/DONE/REMOVE line.""",
)

# Audio
SAMPLE_RATE = _env_int("SAMPLE_RATE", 16000)
CHANNELS = _env_int("CHANNELS", 1)
CHUNK_SIZE = _env_int("CHUNK_SIZE", 1024)
RECORD_SECONDS = _env_int("RECORD_SECONDS", 15)
SILENCE_THRESHOLD = _env_float("SILENCE_THRESHOLD", 0.01)
MIN_SPEECH_LENGTH = _env_float("MIN_SPEECH_LENGTH", 0.2)
# End speech ~300ms after silence (energy VAD)
SILENCE_END_MS = _env_int("SILENCE_END_MS", 300)

# Whisper – use tiny + faster-whisper for ~2–4s (vs 10s+ with stock)
USE_FASTER_WHISPER = _env_bool("USE_FASTER_WHISPER", True)
WHISPER_MODEL = _env("WHISPER_MODEL", "tiny")
WHISPER_DEVICE = _env("WHISPER_DEVICE", "cpu")
WHISPER_LANGUAGE = os.environ.get("WHISPER_LANGUAGE") or None

# Playback – subprocess avoids ALSA/PyAudio hangs on headless/broken audio
PLAYBACK_METHOD = _env("PLAYBACK_METHOD", "subprocess")  # "pyaudio" or "subprocess"

# Piper TTS
PIPER_MODEL_DIR = _env("PIPER_MODEL_DIR", str(ROOT_DIR / "piper_models"))
PIPER_VOICE = _env("PIPER_VOICE", "en_US-lessac-medium")
PIPER_SAMPLE_RATE = _env_int("PIPER_SAMPLE_RATE", 22050)

# Wake word
WAKE_WORD_ENABLED = _env_bool("WAKE_WORD_ENABLED", True)
PORCUPINE_ACCESS_KEY = _env("PORCUPINE_ACCESS_KEY", "")
WAKE_WORD_BUILTIN = _env("WAKE_WORD_BUILTIN", "porcupine")
WAKE_WORD_SENSITIVITY = _env_float("WAKE_WORD_SENSITIVITY", 0.5)
_ww_paths = _env("WAKE_WORD_KEYWORD_PATHS", "")
WAKE_WORD_KEYWORD_PATHS = []
for p in _ww_paths.split(os.pathsep):
    p = p.strip()
    if not p:
        continue
    path = Path(p)
    if not path.is_absolute():
        path = ROOT_DIR / path
    WAKE_WORD_KEYWORD_PATHS.append(str(path))

# Wake word SFX – plays when Hey Zap detected, before listening for question
def _resolve_wake_sfx() -> str:
    p = _env("WAKE_SFX_PATH", "")
    if p:
        path = Path(p)
        if not path.is_absolute():
            path = ROOT_DIR / path
        if path.exists():
            return str(path)
    for rel in ["assets/heyzap.mp3", "core/heyzap.mp3"]:
        cand = ROOT_DIR / rel
        if cand.exists():
            return str(cand)
    return ""

WAKE_SFX_PATH = _resolve_wake_sfx()

# Google + warning daemon (voice-only; no streaming LLM/TTS)
GOOGLE_PREWARM = _env_bool("GOOGLE_PREWARM", True)
WARNING_DAEMON_ENABLED = _env_bool("WARNING_DAEMON_ENABLED", True)

LOG_LEVEL = _env("LOG_LEVEL", "INFO")
LOG_FORMAT = _env("LOG_FORMAT", "%(asctime)s [%(levelname)s] %(name)s: %(message)s")
