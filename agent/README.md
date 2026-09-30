# LiveKit Voice Agent Setup

This agent is a standalone Python program that handles real-time voice interactions using LiveKit.

## 1. Prerequisites
- A LiveKit account (Cloud or Self-hosted).
- API Key and Secret from your LiveKit dashboard.
- Ollama running locally with `gemma3:1b` pulled.

## 2. Configuration
Ensure your `api/.env` file has the following:
- `LIVEKIT_URL`: Your LiveKit project URL (starts with wss://).
- `LIVEKIT_API_KEY`: Your project API Key.
- `LIVEKIT_API_SECRET`: Your project API Secret.
- `LIVEKIT_AGENT_NAME`: `voice-assistant`

## 3. Installation
Run these commands in your terminal:
```bash
# Navigate to the agent folder
cd agent

# Install dependencies
pip install livekit-agents livekit-plugins-ollama livekit-plugins-silero livekit-plugins-deepgram python-dotenv
```

## 4. Running the Agent
To start the voice agent, run:
```bash
python agent.py dev
```
The agent will now wait for a user to join the LiveKit room.
