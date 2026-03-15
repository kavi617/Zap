Please do the following refactors to the Zap project:
Cleanup

Delete all unnecessary files and folders, keep the project clean and minimal

File Structure
Reorganize everything into exactly two folders:

/core — model, voice engine, wake word, session memory, and config
/features — planner and any other feature modules

Wake Word SFX

When the wake word 'Hey Zap' is detected, immediately play heyzap.mp3 before any processing begins
The sound should play from the /core folder or an /assets folder at the root
Make sure the audio plays fully before Zap starts listening for the question

Keep all imports and file paths updated to reflect the new structure. Do not break any existing functionality during the reorganization.