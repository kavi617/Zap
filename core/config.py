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

# Ollama – num_predict caps tokens for faster replies
OLLAMA_BASE_URL = _env("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = _env("OLLAMA_MODEL", "smollm2:135m")
OLLAMA_TIMEOUT = _env_int("OLLAMA_TIMEOUT", 60)
OLLAMA_NUM_PREDICT = _env_int("OLLAMA_NUM_PREDICT", 80)

# Tutor + planner system prompt
SYSTEM_PROMPT = _env(
    "SYSTEM_PROMPT",
    """You are a student voice assistant: tutor and homework planner. Be accurate and brief for voice (1-3 sentences when possible).
Rules: Use simple language. Give clear final answers. For math, show key steps then answer.
Homework commands (reply in one short sentence, then on a NEW LINE output exactly one of):
- To add: ADD|subject|assignment name|due date and time|estimated time 
- To list: LIST
- To mark done: DONE|assignment name or number
- To remove: REMOVE|assignment name or number
If the user just asks a question (no homework command), answer only. No ADD/LIST/DONE/REMOVE line.""",
)

# Audio
SAMPLE_RATE = _env_int("SAMPLE_RATE", 16000)
CHANNELS = _env_int("CHANNELS", 1)
CHUNK_SIZE = _env_int("CHUNK_SIZE", 1024)
RECORD_SECONDS = _env_int("RECORD_SECONDS", 10)
SILENCE_THRESHOLD = _env_float("SILENCE_THRESHOLD", 0.01)
MIN_SPEECH_LENGTH = _env_float("MIN_SPEECH_LENGTH", 0.5)

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

# Addon: Google, streaming TTS, warning daemon
USE_STREAMING_TTS = _env_bool("USE_STREAMING_TTS", True)
GOOGLE_PREWARM = _env_bool("GOOGLE_PREWARM", True)
WARNING_DAEMON_ENABLED = _env_bool("WARNING_DAEMON_ENABLED", True)

LOG_LEVEL = _env("LOG_LEVEL", "INFO")
LOG_FORMAT = _env("LOG_FORMAT", "%(asctime)s [%(levelname)s] %(name)s: %(message)s")
