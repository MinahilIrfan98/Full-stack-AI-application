# CLAUDE.md - Project Guide

This document provides a high-level overview of the project architecture, setup instructions, and coding conventions for the AI Assistant project.

## 🏗 Architecture
The project is a full-stack AI application consisting of three main components:

1.  **Web Frontend (`/web`)**: Next.js 16 application. Provides a chat interface for text and image interactions.
2.  **Backend API (`/api`)**: FastAPI (Python 3.13) server. Orchestrates AI providers (Ollama, etc.) and handles streaming responses.
3.  **Voice Agent (`/agent`)**: Standalone Python process using LiveKit to handle real-time audio conversations.

## 🚀 How to Run

### 1. Backend API
```bash
cd api
uv sync
uv run fastapi dev
```
- **URL**: `http://localhost:8000`

### 2. Web Frontend
```bash
cd web
npm install
npm run dev
```
- **URL**: `http://localhost:3000`

### 3. Voice Agent
```bash
cd agent
pip install -r requirements.txt  # Or install manually as per agent/README.md
python agent.py dev
```

## 🛠 AI Setup
- **Local LLM**: Install [Ollama](https://ollama.ai/).
- **Required Models**:
  - `ollama pull gemma3:1b` (for chat and voice)
  - `ollama pull llava` (for image vision)

## 📜 Coding Conventions

### Backend (Python)
- **Tooling**: Use `uv` for dependency management and `Ruff` for linting.
- **Patterns**: 
  - Follow the Service-Provider pattern: `Route` $\rightarrow$ `Service` $\rightarrow$ `Provider`.
  - Use Pydantic models for all request/response schemas.
  - Keep logic out of `main.py` and move it to `services/` or `providers/`.

### Frontend (TypeScript/React)
- **Tooling**: Next.js App Router, Tailwind CSS 4, shadcn/ui.
- **Patterns**: 
  - Use custom hooks (e.g., `use-chat.ts`) for state management.
  - Keep components small and focused in `components/`.
  - Use `lib/api.ts` as the single point of contact for backend requests.

### General
- **Environment**: Never commit `.env` files. Use `.env.example` for templates.
- **Commits**: Keep commit messages clear and focused on one feature/fix.
