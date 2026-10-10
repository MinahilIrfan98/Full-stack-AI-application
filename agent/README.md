# LiveKit Gemini Realtime Voice Agent

The worker in `agent.py` connects to a LiveKit room and uses Gemini Live for speech-to-speech conversation. It loads its Google API key and agent name from `api/.env`. The web app obtains a room token from the FastAPI `POST /api/voice/token` endpoint.

## Requirements

- Python 3.11 or newer.
- A configured LiveKit Cloud project or self-hosted LiveKit server.
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey).
- The repository's FastAPI API running for browser token requests.

Add these settings to `api/.env`:

```dotenv
GOOGLE_API_KEY=your-google-ai-studio-key
LIVEKIT_URL=wss://your-livekit-host
LIVEKIT_API_KEY=your-livekit-api-key
LIVEKIT_API_SECRET=your-livekit-api-secret
LIVEKIT_AGENT_NAME=voice-assistant
```

Keep `api/.env` private; `.env` files are ignored by Git.

## Install

Run from the repository root:

```bash
cd agent
python -m venv .venv
```

Activate the environment and install the LiveKit Google plugin:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
python -m pip install "livekit-agents[google]>=1.8.2" python-dotenv
```

```bash
# macOS / Linux
source .venv/bin/activate
python -m pip install "livekit-agents[google]>=1.8.2" python-dotenv
```

The `google` extra provides `livekit.plugins.google`. This agent does not use Deepgram, Ollama, Silero, or separate speech-to-text and text-to-speech services.

## Run

From the `agent/` directory, with the virtual environment activated:

```bash
python agent.py dev
```

The worker registers using `LIVEKIT_AGENT_NAME` (default: `voice-assistant`) and waits for the API to dispatch it into a room when a user requests a voice session.

## What the agent runs

`agent.py` uses `google.realtime.RealtimeModel` with `gemini-3.1-flash-live-preview` and the `Puck` voice. Gemini processes incoming speech and generates spoken responses in a single realtime session. The agent greets the user when it joins and is instructed to keep responses short and clear. `GOOGLE_API_KEY` stays in the server-side worker and is not sent to the browser.
