# Zap – Voice-Only Student Assistant

**100% voice-operated.** Planner, Google Calendar / Docs / Gmail (optional OAuth), streaming TTS, and a due-soon warning daemon.

## Folder structure

```
Ai_voice_assistant/
├── main.py
├── requirements.txt
├── .env
├── core/
│   ├── config.py
│   ├── credentials.json   # OAuth client (not in git — copy yours)
│   ├── token.json         # Created after first Google login
│   ├── session.py
│   ├── tts_stream.py      # Chunked streaming playback
│   ├── llm_stream.py      # Ollama streaming deltas
│   ├── warning_daemon.py  # Checks every 5 min for due-within-1-hour
│   └── voice/             # input, stt, llm, tts, output
├── features/
│   ├── planner.py
│   └── google/            # auth, calendar, docs, gmail, router
└── assets/                # heyzap.mp3, warning.mp3 (optional)
```

## Run

```bash
pip install -r requirements.txt
ollama pull qwen2:0.5b   # or your OLLAMA_MODEL
python main.py
```

### Google credentials

See **`CREDENTIALS.md`**. Short version:

1. Create a **Desktop** OAuth client in Google Cloud and download the JSON.
2. Save it as **`core/credentials.json`** (use `core/credentials.example.json` as a template).
3. First run: browser opens once; **`core/token.json`** is created after you sign in.

Porcupine and other keys go in **`.env`** (copy from `.env.example`).

First run with Google: a browser may open for OAuth; **`core/token.json`** is saved after you sign in.

## Google (see `addon.md`)

- **Calendar:** e.g. “What’s due this week?”, “Add math homework due Friday at 3 PM.”
- **Docs:** e.g. “Write me an essay about WW2”, “Update my essay intro” (uses most recent doc).
- **Gmail:** e.g. “Anything important in my Gmail?” — summarizes unread (not full bodies).

If Google APIs fail, Zap says a short error and still answers other questions.

## Warning SFX

Add **`assets/warning.mp3`** for alerts when something is due within an hour (calendar + planner). If the file is missing, Zap still announces by voice.

## Env flags

| Variable | Meaning |
|----------|---------|
| `USE_STREAMING_TTS` | Stream Ollama + chunked Piper playback (default true) |
| `GOOGLE_PREWARM` | Warm Google clients on startup |
| `WARNING_DAEMON_ENABLED` | Background due-soon checks every 5 minutes |

## Speed

- `USE_FASTER_WHISPER=true`, `PLAYBACK_METHOD=subprocess`, `OLLAMA_NUM_PREDICT=80`
