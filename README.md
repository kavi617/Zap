# Zap – Voice Student Assistant

Offline-capable voice loop with **Whisper**, **Ollama**, **Piper** TTS, optional **Porcupine** wake word, **homework planner** (SQLite), and optional **Google** Calendar / Docs / Gmail via OAuth.

## Features

- **Wake word** + optional `assets/heyzap.mp3` (non-blocking — STT can start immediately).
- **Fast VAD** — recording ends ~**300 ms** after silence (`SILENCE_END_MS` in `.env`).
- **Streaming TTS** — text queue → synthesize → play (chunked, low gaps).
- **Google** (optional): calendar (natural language), rich **Docs** (headings + bold), **Gmail** summaries (no full bodies read aloud).
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
│   ├── tts_stream.py         # Streaming TTS pipeline
│   ├── llm_stream.py         # Ollama streaming deltas
│   ├── warning_daemon.py
│   └── voice/                # input, stt, llm, tts, output
├── features/
│   ├── planner.py
│   └── google/
│       ├── auth.py
│       ├── calendar.py
│       ├── docs.py
│       ├── docs_format.py    # Markdown → Docs API requests
│       ├── gmail.py
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

1. Create a **Desktop** OAuth client in Google Cloud (Calendar, Docs, Gmail readonly APIs enabled).
2. Save JSON as **`core/credentials.json`** (see `CREDENTIALS.md` / `core/credentials.example.json` if present).
3. First run opens a browser once; **`core/token.json`** is created.

### Env highlights

| Variable | Meaning |
|----------|---------|
| `USE_STREAMING_TTS` | Stream Ollama phrases + pipeline TTS (default: true) |
| `SILENCE_END_MS` | Silence duration to stop recording (default: 300) |
| `GOOGLE_PREWARM` | Background calendar cache + Gmail prefetch |
| `WARNING_DAEMON_ENABLED` | Due-soon checks every 5 minutes |
| `USE_FASTER_WHISPER` | Faster Whisper for STT |
| `PLAYBACK_METHOD` | `subprocess` (aplay/ffplay) or `pyaudio` |

If Google APIs fail, Zap says *"I'm having trouble connecting to Google right now"* and continues with local Q&A and planner.

## Docs

- **`addon.md`** — product spec for the performance/UX overhaul.
- **`ADDON_IMPLEMENTATION.md`** — what was implemented and which files changed.
