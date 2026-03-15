# Zap – Voice-Only Student Assistant

**100% voice-operated.** No UI. Session memory for follow-up questions; planner fully voice-controlled.

## Folder structure

```
Ai_voice_assistant/
├── main.py              # Entry point
├── requirements.txt
├── .env                  # Optional: PORCUPINE_ACCESS_KEY, OLLAMA_MODEL, etc.
├── assets/               # Put heyzap.mp3 here for wake word SFX
├── data/                 # Runtime (planner.db)
│
├── core/                 # Model, voice engine, wake word, session, config
│   ├── config.py
│   ├── session.py
│   └── voice/
│       ├── input.py     # Wake word + recording
│       ├── stt.py       # Whisper
│       ├── llm.py       # Ollama
│       ├── tts.py       # Piper
│       └── output.py    # Playback + wake SFX
│
└── features/             # Planner and other feature modules
    └── planner.py
```

## Run

```bash
pip install -r requirements.txt
ollama pull qwen2:0.5b
python main.py
```

Say **Hey Zap**, then ask questions or use planner commands. The wake word plays `assets/heyzap.mp3` (or `core/heyzap.mp3`) if present, then listens for your question.

## Wake word SFX

Place **heyzap.mp3** in `assets/` or `core/`. When the wake word is detected, it plays fully before Zap starts listening. Set `WAKE_SFX_PATH` in `.env` to override the path.

## Speed (target 5–10s total)

- **Whisper:** `USE_FASTER_WHISPER=true` uses faster-whisper (~2–4s vs 10s+)
- **Playback:** `PLAYBACK_METHOD=subprocess` uses `aplay`/`paplay`/`ffplay` to avoid PyAudio/ALSA hangs
- **LLM:** `OLLAMA_NUM_PREDICT=80` limits reply length

On Linux, install `alsa-utils` (aplay) or `ffmpeg` (ffplay) for reliable playback.
