"""
Competition-style terminal output: colors, banner, structured lines.
Use instead of raw logging for user-visible flow.
"""
import os
import sys

# ANSI (Windows Terminal / modern consoles)
_G = "\033[92m"
_Y = "\033[93m"
_R = "\033[91m"
_C = "\033[96m"
_M = "\033[95m"
_DIM = "\033[2m"
_RESET = "\033[0m"
_BOLD = "\033[1m"


def _supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR", "").strip() == ""


def _c(s: str, code: str) -> str:
    if not _supports_color():
        return s
    return f"{code}{s}{_RESET}"


def clear_screen() -> None:
    if os.name == "nt":
        os.system("cls")
    else:
        sys.stdout.write("\033[2J\033[H")


def banner() -> None:
    box = f"""{_c("╔══════════════════════════════════════════╗", _C)}
{_c("║", _C)}         {_BOLD}ZAP AI VOICE ASSISTANT{_RESET}{_c("           ║", _C)}
{_c("║", _C)}   Raspberry Pi · Whisper · Ollama        {_c("║", _C)}
{_c("╚══════════════════════════════════════════╝", _C)}
"""
    sys.stdout.write(box)


def divider() -> None:
    sys.stdout.write(_c("──────────────────────────────────────────\n", _DIM))


def system_ok(msg: str) -> None:
    sys.stdout.write(f"{_c('[SYSTEM]', _G)} {_c('✓', _G)} {msg}\n")


def system_processing(msg: str) -> None:
    sys.stdout.write(f"{_c('[SYSTEM]', _Y)} {msg}\n")


def system_ready() -> None:
    sys.stdout.write(
        f"{_c('[SYSTEM]', _G)} {_c('✓', _G)} Ready — say Hey Zap to continue\n",
    )


def wake() -> None:
    sys.stdout.write(f"{_c('[WAKE]', _M)}    Wake word detected\n")


def stt_line(seconds: float) -> None:
    if seconds >= 1.0:
        sys.stdout.write(
            f"{_c('[STT]', _Y)}     Transcribing... ({seconds:.1f}s)\n",
        )
    else:
        sys.stdout.write(f"{_c('[STT]', _Y)}     Transcribing... done\n")


def you_spoke(text: str) -> None:
    t = text.replace("\n", " ")[:200]
    sys.stdout.write(f"{_c('[YOU]', _C)}     \"{t}\"\n")


def intent_line(text: str) -> None:
    sys.stdout.write(f"{_c('[INTENT]', _Y)} {text}\n")


def doc_created(title: str) -> None:
    sys.stdout.write(
        f"{_c('[DOC]', _G)}     {_c('✓', _G)} Created: \"{title}\"\n",
    )


def doc_opened() -> None:
    sys.stdout.write(f"{_c('[DOC]', _G)}     {_c('✓', _G)} Opened in browser\n")


def zap_reply_preview(text: str) -> None:
    t = text.replace("\n", " ")[:120]
    sys.stdout.write(f"{_c('[ZAP]', _G)}     \"{t}\"\n")


def audio_streaming() -> None:
    sys.stdout.write(f"{_c('[AUDIO]', _M)}   Streaming response...\n")


def warn_daemon(event_name: str) -> None:
    sys.stdout.write(
        f"{_c('[WARN]', _Y)}   Due soon: {event_name}\n",
    )


def error_line(msg: str) -> None:
    sys.stdout.write(f"{_c('[ERROR]', _R)} {msg}\n")


def install_stderr_filter() -> None:
    """Suppress ALSA / JACK / PortAudio spam to stderr."""
    real = sys.stderr

    class _F:
        def write(self, s: str) -> int:
            if not isinstance(s, str):
                s = str(s)
            skip = (
                "ALSA lib",
                "JackShm",
                "jack server",
                "Cannot connect to server socket",
                "pcm_",
                "snd_",
                "GPU device discovery",
                "ReadFileContents Failed",
                "onnxruntime",
            )
            if any(x in s for x in skip):
                return len(s)
            real.write(s)
            return len(s)

        def flush(self) -> None:
            real.flush()

    sys.stderr = _F()  # type: ignore[assignment]
