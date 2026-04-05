# Addon implementation (performance & UX overhaul)

This document lists what was added or changed to match `addon.md` (VAD, non-blocking wake SFX, Google services, terminal UI, and error handling). The voice path is **non-streaming**: one LLM response, then Piper TTS.

## New files

| Path | Purpose |
|------|---------|
| `core/console_ui.py` | Colored, structured terminal output (banner, `[SYSTEM]`, `[WAKE]`, `[STT]`, `[YOU]`, `[AUDIO]`, `[WARN]`, `[ERROR]`). |
| `features/google/docs_format.py` | Builds Google Docs `batchUpdate` requests from Markdown-like content (`##`, `###`, `**bold**`). |

## Modified files

| Path | Changes |
|------|---------|
| `main.py` | Installs stderr filter before other imports; clears screen and prints banner; uses `console_ui` for status lines; `llm.respond` → `tts.speak`; Google calendar prewarm cache; logging default WARNING. |
| `core/voice/input.py` | Wake SFX in a **daemon thread** (returns immediately). **VAD**: `SILENCE_END_MS` (default **300 ms**). Removed hardcoded `input_device_index`. |
| `core/config.py` | `SILENCE_END_MS`, voice-style `SYSTEM_PROMPT`; Ollama / Google / daemon flags. |
| `core/warning_daemon.py` | `[WARN]` line via `console_ui` when alerting. |
| `features/google/auth.py` | User-facing Google error string. |
| `features/google/calendar.py` | `list_tomorrow_events`, `find_upcoming_events_matching`, `format_events_conversational`. |
| `features/google/docs.py` | **`create_document_rich`** with `docs_format`. |
| `features/google/router.py` | **Thread pool** for Google calls; expanded intents; Docs Markdown; calendar NL (dateparser + manual time fallback). |

## Behaviour summary

1. **TTS** — Full reply synthesized once via `core/voice/tts.py` after the LLM returns.
2. **Wake sound** — Non-blocking thread.
3. **VAD** — ~300 ms configurable silence end.
4. **Google Calendar** — Week, tomorrow, add, move/reschedule.
5. **Google Docs** — Rich formatting from Markdown; short voice confirmation.
6. **Google** — Calendar + Docs only (no Gmail).
7. **Terminal** — Banner, colors, stderr filter.
8. **Errors** — Friendly voice + `[ERROR]` line; loop continues.

## Credentials

- `core/credentials.json` and `core/token.json` — see `CREDENTIALS.md` (gitignored).

## Assets

- `assets/heyzap.mp3`, `assets/warning.mp3` — optional SFX.
