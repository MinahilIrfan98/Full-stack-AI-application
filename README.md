# OpenChat AI Assistant

OpenChat is a self-hosted AI chat application with a Next.js web client, a FastAPI API, and an optional LiveKit voice worker. Chat and image requests can use local Ollama or configured cloud providers. The voice worker uses Gemini Live through LiveKit's Google plugin.

## Features

- Server-sent event (SSE) streaming for chat.
- Ollama models and optional Anthropic, OpenAI-compatible, Gemini, Grok, and Meta providers.
- Image attachments for vision-capable models.
- Text, Markdown, CSV, JSON, source code, PDF, and DOCX file attachments.
- Large document retrieval using Ollama embeddings and an in-memory per-upload index.
- Browser-local conversation history, dark mode, and light mode.
- Optional Gemini realtime voice sessions through LiveKit.

## Repository layout

```text
api/                       FastAPI backend and Python tests
  app/
    core/                  Environment-based configuration and logging
    providers/             Ollama and cloud provider adapters
    routes/                Health, models, upload, chat, and voice-token routes
    services/              Chat streaming and file retrieval
  tests/                   Pytest API tests
web/                       Next.js frontend
  app/                     App Router pages and global styles
  components/chat/         Chat UI, composer, model picker, and voice call
  components/ui/           Shared UI primitives
  hooks/                   Chat and model state
  lib/                     API client, types, and helpers
agent/                     Optional LiveKit Gemini realtime voice worker
  agent.py                 Worker entry point
  README.md                Voice agent setup and commands
docker-compose.yml         API and web services; optional Ollama profile
```

## Requirements

- Node.js 20.9 or newer (Node.js 24 recommended).
- Python 3.13 and [`uv`](https://docs.astral.sh/uv/).
- [Ollama](https://ollama.com/) for local chat, images, and large-file retrieval.
- Optional cloud provider keys for cloud chat and image support.
- Optional LiveKit project and Gemini API key for realtime voice.

## Run locally

### 1. Configure the API

From the repository root, copy the example settings file if it exists, then edit `api/.env` with the settings you need. The file is ignored by Git; do not commit credentials.

```powershell
# Windows PowerShell
Copy-Item api/.env.example api/.env
```

```bash
# macOS / Linux
cp api/.env.example api/.env
```

For local chat, run Ollama and pull a model:

```bash
ollama pull gemma3:1b
```

For image questions, install a vision model supported by Ollama (for example, `llava`) and select it in the app. Large document retrieval uses `nomic-embed-text`; the API attempts to pull it when needed.

### 2. Start the API

In a terminal at the repository root:

```bash
cd api
uv sync
uv run fastapi dev app/main.py
```

The API runs at <http://localhost:8000>; interactive docs are at <http://localhost:8000/docs>.

### 3. Start the web app

In a second terminal:

```bash
cd web
npm install
npm run dev
```

Open <http://localhost:3000>. The Next.js server forwards `/api/*` requests to the backend at `http://localhost:8000` by default.

## Voice agent (optional)

The browser requests a room token from FastAPI; the API dispatches the configured worker to LiveKit. The worker reads `GOOGLE_API_KEY` and `LIVEKIT_AGENT_NAME` from `api/.env` and uses Gemini Live (`gemini-3.1-flash-live-preview`) for speech-to-speech. No Deepgram or local Ollama service is used by the voice agent.

Add these values to `api/.env`:

```dotenv
GOOGLE_API_KEY=your-google-ai-studio-key
LIVEKIT_URL=wss://your-livekit-host
LIVEKIT_API_KEY=your-livekit-api-key
LIVEKIT_API_SECRET=your-livekit-api-secret
LIVEKIT_AGENT_NAME=voice-assistant
```

Install and start the worker in a third terminal:

```bash
cd agent
python -m venv .venv
```

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
python -m pip install "livekit-agents[google]>=1.8.2" python-dotenv
python agent.py dev
```

```bash
# macOS / Linux
source .venv/bin/activate
python -m pip install "livekit-agents[google]>=1.8.2" python-dotenv
python agent.py dev
```

The Gemini key is read by the worker on the server and is not sent to the browser. See [agent/README.md](agent/README.md) for complete voice setup instructions.

## Configuration

The API reads settings from environment variables and `api/.env`. Common settings include:

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server address. |
| `OLLAMA_ENABLED` | `true` | Enable the local Ollama provider. |
| `ALLOW_CLOUD_FALLBACK` | `true` | Allow configured cloud providers if a model fails before streaming begins. |
| `MAX_UPLOAD_MB` | `4` | Maximum upload size in megabytes. |
| `REQUEST_TIMEOUT_SECONDS` | `120` | Cloud provider request timeout. |
| `OLLAMA_TIMEOUT_SECONDS` | `600` | Ollama request timeout. |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed origins for direct browser-to-API requests. |
| `GOOGLE_API_KEY` | unset | Gemini Live API key used by the optional voice worker. |
| `LIVEKIT_URL` | unset | LiveKit server URL. |
| `LIVEKIT_API_KEY` | unset | LiveKit API key used by FastAPI. |
| `LIVEKIT_API_SECRET` | unset | LiveKit API secret used by FastAPI. |
| `LIVEKIT_AGENT_NAME` | `voice-assistant` | Worker name used for LiveKit dispatch. |

Cloud chat providers use their respective API key settings in `api/.env`. The API keys remain server-side and are not exposed to the web client.

## File uploads and retrieval

Uploads up to 4 MB use extracted text as direct context, capped at 8,000 characters. Larger files are chunked, embedded with Ollama's `nomic-embed-text`, and kept in an in-memory index for the running API process. If the API restarts, attach the large file again. Increase `MAX_UPLOAD_MB` for local use if needed, then restart the API.

## Docker Compose

Configure `api/.env`, then start the API and web services:

```bash
docker compose up --build
```

Open the web app at <http://localhost:3000>. The API is available at <http://localhost:8000>. To also run Ollama in Docker, use its optional profile:

```bash
docker compose --profile ollama up --build
```

When using that profile, set `OLLAMA_HOST=http://ollama:11434` for the API.

## Development checks

API checks:

```bash
cd api
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Frontend checks:

```bash
cd web
npm run typecheck
npm run build
```

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Health check. |
| `GET` | `/api/models` | Lists available local and configured cloud models. Add `?refresh=true` to bypass the short cache. |
| `POST` | `/api/upload` | Extracts supported document text or indexes a large document. Multipart field: `file`. |
| `POST` | `/api/chat` | Streams a response as SSE. |
| `POST` | `/api/voice/token` | Issues a short-lived LiveKit participant token and dispatches the configured voice worker. |

## Troubleshooting

- **No model appears:** Check that Ollama is running and a chat model is installed (`ollama list`), or configure a cloud provider key.
- **Image questions fail:** Select a vision-capable model.
- **Large-file indexing fails:** Confirm Ollama is reachable and `nomic-embed-text` can be pulled and run.
- **Voice is unavailable:** Check the LiveKit settings in `api/.env`, confirm the worker is running, and verify `GOOGLE_API_KEY` is set.
- **The web app cannot reach the API:** Confirm the backend is running on port 8000. If it uses a different URL, set `API_URL` for the Next.js server and restart it.
