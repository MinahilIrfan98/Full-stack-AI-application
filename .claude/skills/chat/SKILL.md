# Chat Feature Skill

This skill describes the implementation of the core text-based chat functionality.

## How it Works
The chat feature uses a streaming architecture to provide real-time responses.

### 1. Data Flow
- **Frontend**: The `web/components/chat/composer.tsx` captures user input and calls `streamChat` in `web/lib/api.ts`.
- **Backend Route**: `api/app/routes/chat.py` receives the request and delegates to the `ChatService`.
- **Service Layer**: `api/app/services/chat.py` handles provider selection and manages the fallback logic.
- **Provider**: `api/app/providers/ollama.py` communicates with the local Ollama instance using the official SDK.

### 2. Streaming Mechanism
The project uses **Server-Sent Events (SSE)**. This allows the backend to "push" tokens to the frontend as they are generated, rather than waiting for the entire answer to be finished.

### 3. Tech Stack
- **Frontend**: React 19, Next.js 16.
- **Backend**: FastAPI, Python 3.13.
- **AI**: Ollama (Local).
