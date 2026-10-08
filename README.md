# OpenChat AI Assistant

A chat app I built that handles text, images, documents and voice. The models run on your own machine through Ollama, so your messages stay local unless you pick a cloud model yourself.

Live demo: https://full-stack-ai-application-three.vercel.app

The deployed version can't reach an Ollama running on my laptop, so it only works with a cloud model selected.

## What it does

Replies stream in token by token over Server-Sent Events, which makes the chat feel like someone is typing back.

You can attach a photo and ask about it. A vision model (llava) looks at the image and answers.

You can also attach a document: txt, md, csv, json, source code, pdf or docx. The backend pulls the text out of the file, passes it to the model along with your question, and the answer is based on what the file says. The attached file shows up as a small chip above your message, so the chat history keeps track of what you uploaded. Files are limited to 4 MB.

For voice, a Python agent joins a LiveKit room, listens, thinks with Ollama and talks back with low delay.

## How the pieces connect

For text, images and files the path is browser, then Next.js, then FastAPI, then Ollama, and the answer streams back the same way.

For voice the browser joins a LiveKit room, the Python agent in the same room picks up the audio, sends it through Ollama and speaks the reply.

The repo has three folders: `web` for the Next.js frontend, `api` for the FastAPI backend, and `agent` for the voice agent.

## Tech stack

| Part | What I used |
| --- | --- |
| Frontend | Next.js 16, React 19, Tailwind CSS 4, shadcn/ui |
| Backend | FastAPI on Python 3.13, managed with uv |
| File reading | pypdf for PDFs, python-docx for Word files |
| Voice | LiveKit, Deepgram for speech to text |
| Models | Ollama with Gemma 3 for chat and llava for images |

## Running it locally

You need Ollama, Node.js, Python 3.13 and uv installed. The app needs three terminals open at the same time, one each for the backend, frontend and (optionally) the voice agent.

Start with the models:

```bash
ollama pull gemma3:1b
ollama pull llava
```

Backend:

```bash
cd api
cp .env.example .env   # then fill in your values
uv sync
uv run fastapi dev
```

Frontend:

```bash
cd web
npm install
npm run dev
```

Open http://localhost:3000. If the page says it can't reach the AI server, the backend isn't running yet.

Voice agent, only if you want voice:

```bash
cd agent
pip install livekit-agents livekit-plugins-ollama livekit-plugins-silero livekit-plugins-deepgram python-dotenv
python agent.py dev
```

One thing that cost me time: `fastapi dev` restarts itself whenever a file in `api` changes. If you generate test files inside that folder, the server keeps reloading while you're trying to chat.

## Configuration

Secrets live in `.env` files, which are git-ignored. Don't commit them.

| Variable | Used for |
| --- | --- |
| `OLLAMA_BASE_URL` | Address of your Ollama server |
| `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | Voice rooms |
| `DEEPGRAM_API_KEY` | Speech to text for the voice agent |

## API routes

| Route | Purpose |
| --- | --- |
| `GET /api/health` | Quick check that the backend is up |
| `GET /api/models` | Lists the models the UI can choose from |
| `POST /api/chat` | Sends a message and streams the reply |
| `POST /api/upload` | Takes a file and returns its extracted text |

## Known limits

Uploads over 4 MB are rejected. That keeps it inside what Vercel allows too.

A scanned PDF is just pictures of pages, so there is no text to extract. It needs OCR first, which this project doesn't do.

Small local models like gemma3:1b struggle with long documents. For anything big, a larger or cloud model gives much better answers.
