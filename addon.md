This is an addon to the existing Zap AI Voice Assistant project. Do not break any existing functionality. Implement the following features using the credentials.json file already in the /core folder:
Google Calendar Integration

Connect to Google Calendar API using OAuth from credentials.json
Voice commands like 'add homework due Friday' or 'what's due this week?' should create, read, and edit calendar events
Run a background daemon thread that checks every 5 minutes for assignments due within the next hour
When an assignment is within 1 hour of its due time, immediately play warning.mp3 as an audio alert then have Zap announce it by voice
Store the OAuth token in /core/token.json so the user only authenticates once

Google Docs Integration

When the student asks Zap to write an essay, report, or any document, generate the full content with the AI model and create a new Google Doc automatically via the Docs API
Open the created doc link in the default browser after creation
Support commands like 'write me an essay about WW2' or 'create notes on photosynthesis' and put the result directly into a new Google Doc
Also support editing existing docs by voice — 'update my essay intro' should find the most recent relevant doc and edit it

Gmail Integration

Connect Gmail API with readonly scope
When student says anything like 'anything important in my gmail', 'did my teacher email me', or 'check my emails', automatically fetch the last 10 unread emails
Use the AI model to summarize only the important ones, filtering out spam and promotions
Respond with a natural voice summary like 'You have 2 important emails — one from Mrs. Johnson about your project due Monday and one from the school about picture day'
Never read full email bodies out loud, only smart summaries

Streaming TTS for Ultra-Fast Response

Implement a streaming TTS pipeline using Kokoro that works exactly like YouTube buffering
As soon as the AI model generates the first 5-10 words of a response, immediately begin synthesizing and playing that chunk through the speaker
While chunk 1 is playing, synthesize chunk 2 in a background thread, then chunk 3, and so on continuously without any gaps or silence between chunks
Use a thread-safe audio queue so chunks play seamlessly back to back
The goal is that the user hears the first word within 1-2 seconds of asking a question, and the full response feels instant
Split text into chunks at natural punctuation boundaries (commas, periods, 'and', 'but') so speech sounds natural not robotic

Speed Optimizations — Target Under 5 Second Total Response Time

Pre-warm the AI model and Kokoro TTS pipeline on startup so first response is not slow
Cache Google API tokens and connections — never re-authenticate mid-session
Run Gmail checks, Calendar checks, and the warning daemon all as separate background threads so they never block voice input
Use async API calls for all Google services
Pre-load the most recent calendar events and unread email count into memory on startup so responses to planning questions are instant

File Structure

All Google integration code goes in /features/google/ with separate files: calendar.py, docs.py, gmail.py, auth.py
Streaming TTS logic goes in /core/tts_stream.py
Warning daemon goes in /core/warning_daemon.py
All credentials stay in /core/credentials.json and /core/token.json

Error Handling

If Google API fails or internet is down, Zap should say 'I am having trouble connecting to Google right now' and continue working for non-Google questions
Never crash the main voice loop due to a Google API error
Retry failed API calls once silently before giving up

Keep all existing wake word, session memory, SFX, and planner functionality fully intact. This is purely additive.