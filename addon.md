This is a performance and UX overhaul of the existing Zap AI Voice Assistant. Do not break any existing functionality — this is purely improvements and fixes to what is already implemented.

1. Streaming TTS — zero gaps, fully continuous audio
The current streaming has too much silence between chunks and feels choppy. Fix it completely:

Use a producer/consumer queue with a dedicated audio playback thread
Start playing the first chunk the moment it's ready — do not wait for the full response
While chunk 1 plays, synthesize chunk 2 in the background, then chunk 3, seamlessly
Zero silence between chunks — audio must feel like one continuous stream
Split text at natural boundaries (periods, commas, "and", "but") so speech sounds human
Never block the LLM stream waiting for audio to finish

2. Non-blocking wake sound
The wake SFX (assets/heyzap.mp3) must play in a background thread the instant the wake word fires. Whisper transcription must begin immediately in parallel — do not wait for the SFX to finish before starting STT.
3. Fast end-of-speech detection
Stop recording within 300ms of the user going silent. Use energy-based VAD. Do not use fixed-length recording windows. The current wait time after the user stops talking is too long — cut it aggressively.
4. Fully concurrent pipeline
All stages must run in parallel background threads with no stage blocking another: wake detection → SFX playback → Whisper STT → LLM inference → TTS generation → audio playback.
5. LLM voice response style
System prompt must instruct the LLM to keep voice responses short, natural, and conversational unless the user explicitly requests a document. No bullet points. No long explanations. Sound like a helpful human assistant, not a textbook.

6. Google Calendar — full natural language support
The calendar integration must handle all of these voice patterns naturally:

"Add homework due Friday at 5pm" → create event with correct date/time parsed by dateparser
"What's due this week?" → read back upcoming events in a natural voice summary
"Move my math homework to Saturday" → find and update the existing event
"Do I have anything tomorrow?" → list events for tomorrow conversationally
Always confirm back by voice: "Done, I've added math homework due Friday at 5pm"
The warning daemon must run every 5 minutes in the background, check for events due within 1 hour, play assets/warning.mp3 then announce by voice. Warned events must be stored in data/warning_warned.json so the same event is never announced twice
Never block the voice loop for calendar operations — run all API calls in background threads

7. Google Docs — full complete documents with rich formatting
When the user asks for any written document by voice:

Generate the complete full document using the LLM — no outlines, no meta-commentary, no partial content. Write the actual full essay/report/notes in its entirety
Create the Google Doc via the Docs API with proper formatting:

Document title: clean relevant title only, e.g. "World War II: A Global Conflict" — never a sentence describing the doc
Section headers use HEADING_1 and HEADING_2 paragraph styles
Bold key terms and important phrases using textStyle bold
Proper paragraph spacing between sections


Automatically open the doc link in the browser after creation
Respond by voice with a short confirmation only: "I've created your essay on World War II in Google Docs and opened it for you." Do not read the document aloud
Support editing existing docs: "update my essay intro" → find the most recent relevant doc and edit it
Supported commands include: "write me an essay about X", "create notes on X", "make a report on X", "update my X doc"

8. Gmail — smart summaries only

Triggered by: "anything important in my email", "did my teacher email me", "check my emails"
Fetch last 10 unread emails, filter out spam and promotions
Use the LLM to summarize only important ones
Respond naturally by voice: "You have 2 important emails — one from Mrs. Johnson about your project due Monday, and one from the school about picture day"
Never read full email bodies aloud — smart summaries only
Run Gmail prefetch in a background thread on startup so responses are instant


9. Clean competition-ready terminal — judges are watching
Suppress ALL ALSA, JACK, and PortAudio spam completely at startup by redirecting stderr for those libraries before they load. Then replace all terminal output with a clean structured display:
╔══════════════════════════════════════════╗
║         ZAP AI VOICE ASSISTANT           ║
║   Raspberry Pi 5 · Whisper · Ollama      ║
╚══════════════════════════════════════════╝

[SYSTEM] ✓ Ollama connected
[SYSTEM] ✓ TTS pipeline ready  
[SYSTEM] ✓ Google APIs connected
[SYSTEM] ✓ Warning daemon running
[SYSTEM] ✓ Listening for "Hey Zap"...

──────────────────────────────────────────
[WAKE]    Wake word detected
[STT]     Transcribing... (1.8s)
[YOU]     "Write me an essay about World War II"
[INTENT]  Google Docs → Generating full essay...
[DOC]     ✓ Created: "World War II: A Global Conflict"
[DOC]     ✓ Opened in browser
[ZAP]     "I've created your essay in Google Docs."
[AUDIO]   Streaming response...
──────────────────────────────────────────
[SYSTEM] ✓ Ready — say Hey Zap to continue
Rules for the terminal:

Clear the terminal on startup so output is always clean
Use color: green for ✓ success, yellow for processing, red for errors, cyan for user speech
Show timing only for operations over 1 second, formatted as e.g. (1.8s)
Never show raw stack traces — catch all errors and show [ERROR] <friendly one-line message>
Show [WARN] with the event name when the warning daemon fires
Each new interaction starts with a divider line so sessions are visually separated
Show Google API operations clearly so judges can see what's happening in real time


10. Error handling

If any Google API fails, Zap says "I'm having trouble connecting to Google right now" and continues working for non-Google questions
Never crash the main voice loop due to any Google error
Retry failed API calls once silently before giving up
All credentials stay in core/credentials.json and core/token.json — never move them


Goal: a voice assistant that responds in under 2 seconds, sounds completely natural, handles Google Docs/Calendar/Gmail live on stage, and displays a clean professional terminal that clearly shows judges exactly how the system works in real time. This needs to win first place. 🏆