import os

from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import deepgram, openai, silero

# api/.env ko kisi bhi folder se load karne ke liye
env_path = os.path.join(os.path.dirname(__file__), "..", "api", ".env")
load_dotenv(env_path)

AGENT_NAME = os.getenv("LIVEKIT_AGENT_NAME", "voice-assistant")


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(),
        llm=openai.LLM(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            model="gemma3:1b",
        ),
        tts=deepgram.TTS(),
    )

    await session.start(
        room=ctx.room,
        agent=Agent(
            instructions="You are a friendly voice assistant. Keep answers short and clear."
        ),
    )
    await session.generate_reply(
        instructions="Greet the user and ask how you can help."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name=AGENT_NAME))