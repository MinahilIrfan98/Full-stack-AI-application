# LiveKit Voice Skill

This skill describes the implementation of the real-time voice assistant.

## How it Works
The voice feature is implemented as a standalone **Agent** that lives outside the main API.

### 1. Architecture
- **LiveKit Server**: Acts as the "meeting room" where the user and the AI Agent connect.
- **Voice Agent**: A Python process (`agent/agent.py`) that joins the room as a participant.

### 2. The Voice Pipeline
The agent uses a "Modular Pipeline":
- **VAD (Voice Activity Detection)**: Uses `silero` to detect when the user starts and stops talking.
- **STT (Speech-to-Text)**: Uses `deepgram` to convert the user's audio into text.
- **LLM (The Brain)**: Uses `ollama` (`gemma3:1b`) to process the text and decide what to say.
- **TTS (Text-to-Speech)**: Uses `deepgram` to convert the AI's text back into a natural-sounding voice.

### 3. Execution
The agent is run using the `livekit-agents` CLI, which manages the connection and job lifecycle.
