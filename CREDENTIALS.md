# How to add Google API credentials

Zap reads **`core/credentials.json`** (OAuth **Desktop app** client). It is **not** committed to git. After the first successful login, **`core/token.json`** stores your refresh token.

## 1. Google Cloud Console

1. Open [Google Cloud Console](https://console.cloud.google.com/) and select or create a project.
2. **APIs & Services → Library** — enable:
   - Google Calendar API  
   - Google Docs API  
3. **APIs & Services → OAuth consent screen** — choose **External** (or Internal for Workspace), add your Google account as a **Test user** if the app is in Testing mode.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**  
   - Application type: **Desktop app**  
   - Download the JSON.

## 2. Install the file in this project

1. Copy the downloaded JSON to your project folder.
2. Rename it to **`credentials.json`**.
3. Place it here: **`core/credentials.json`** (same folder as `credentials.example.json`).

You can copy the example and replace values:

```text
copy core\credentials.example.json core\credentials.json
```

Then edit `core/credentials.json` and paste your real `client_id` and `client_secret` from the Google Cloud download.

## 3. First run

Run:

```bash
python main.py
```

The first time a Google feature is used, a browser may open for you to sign in and approve scopes. After that, **`core/token.json`** is created so you usually stay signed in.

If you change which APIs or scopes the app uses, **delete `core/token.json`** and run again so Google can issue a new token.

## 4. Other secrets (not Google)

- **Porcupine** — put `PORCUPINE_ACCESS_KEY` in **`.env`** (see `.env.example`).
- **Wake word file** — `.ppn` path in `.env` as `WAKE_WORD_KEYWORD_PATHS=assets/wake_word.ppn`.

## Troubleshooting

- **Redirect URI mismatch** — In Google Cloud, for a Desktop client, allow `http://localhost` or the port the library prints (sometimes `http://127.0.0.1`).
- **Access blocked** — Add your account under **Test users** on the OAuth consent screen while the app is in Testing mode.
- **Missing `credentials.json`** — Zap will skip Google prewarm; voice features still work without Google.
