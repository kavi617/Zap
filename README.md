# Zap – Voice Student Assistant

Offline-capable voice loop with **Whisper**, **Ollama**, **Piper** TTS, optional **Porcupine** wake word, **homework planner** (SQLite), and optional **Google** Calendar / Docs via OAuth.

## Features

- **Wake word** + optional `assets/heyzap.mp3` (non-blocking — STT can start immediately).
- **VAD** — recording ends after **~1 s** of silence by default (`SILENCE_END_MS`), up to **`RECORD_SECONDS`** max clip length — tune both if you pause mid‑sentence or need longer turns.
- **Voice path** — one Ollama reply, then Piper speaks the full line (no streaming LLM/TTS). Tune `OLLAMA_MODEL`, `OLLAMA_NUM_PREDICT`, and `VOICE_REPLY_MAX_CHARS` for sub‑5s turns when using a small model and short speech.
- **Google** (optional): calendar (create events before listing “tomorrow”), rich **Docs**.
- **Warning daemon** — every 5 minutes, events due within 1 hour: optional `assets/warning.mp3` + voice; deduped in `data/warning_warned.json`.
- **Competition-style terminal** — banner, colored status lines, stderr filter for ALSA/JACK noise (see `core/console_ui.py`).

## Folder structure

```
Ai_voice_assistant/
├── main.py
├── requirements.txt
├── .env
├── ADDON_IMPLEMENTATION.md   # Changelog for addon overhaul
├── CREDENTIALS.md            # OAuth setup
├── core/
│   ├── config.py
│   ├── console_ui.py         # Terminal UX
│   ├── credentials.json      # (you add; gitignored)
│   ├── token.json            # Created after OAuth (gitignored)
│   ├── session.py
│   ├── warning_daemon.py
│   └── voice/                # input, stt, llm, tts, output
├── features/
│   ├── planner.py
│   └── google/
│       ├── auth.py
│       ├── calendar.py
│       ├── docs.py
│       ├── docs_format.py    # Markdown → Docs API requests
│       └── router.py
├── assets/                   # heyzap.mp3, warning.mp3
└── data/                     # planner.db, warning_warned.json
```

## Run

```bash
pip install -r requirements.txt
ollama pull <your-model>   # match OLLAMA_MODEL in .env
python main.py
```

### Google OAuth

1. Create a **Desktop** OAuth client in Google Cloud (**Calendar** + **Docs** APIs enabled). If you signed in before Gmail was removed, delete **`core/token.json`** and sign in again.
2. Save JSON as **`core/credentials.json`** (see `CREDENTIALS.md` / `core/credentials.example.json` if present).
3. First run opens a browser once; **`core/token.json`** is created.

### Env highlights

| Variable | Meaning |
|----------|---------|
| `OLLAMA_NUM_PREDICT` | Max tokens for normal voice replies (default: 56) |
| `OLLAMA_NUM_PREDICT_GOOGLE` | Max tokens for Google Docs create/edit LLM output (default: 4096) |
| `OLLAMA_TIMEOUT_GOOGLE` | Seconds to wait for long Doc generation (default: 180) |
| `LOCAL_TIMEZONE` | IANA zone (e.g. `America/Los_Angeles`) for calendar times; if unset, **auto-detected** from Windows (`tzlocal`) |
| `VOICE_REPLY_MAX_CHARS` | Cap on spoken reply length (default: 220) |
| `SILENCE_END_MS` | Silence after you stop talking before clip ends (default: 1000) |
| `RECORD_SECONDS` | Max recording length cap (default: 30) |
| `GOOGLE_PREWARM` | Background calendar cache |
| `WARNING_DAEMON_ENABLED` | Due-soon checks every 5 minutes |
| `USE_FASTER_WHISPER` | Faster Whisper for STT |
| `PLAYBACK_METHOD` | `subprocess` (aplay/ffplay) or `pyaudio` |

If Google APIs fail, Zap says *"I'm having trouble connecting to Google right now"* and continues with local Q&A and planner.

## Docs

- **`addon.md`** — product spec for the performance/UX overhaul.
- **`ADDON_IMPLEMENTATION.md`** — what was implemented and which files changed.
