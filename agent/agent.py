import os

from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import google

# Load the shared API configuration when starting this agent from any directory.
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api", ".env"))
load_dotenv(env_path)

AGENT_NAME = os.getenv("LIVEKIT_AGENT_NAME", "voice-assistant")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_LIVE_MODEL = "gemini-3.1-flash-live-preview"


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is missing from api/.env")

    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            model=GEMINI_LIVE_MODEL,
            api_key=GOOGLE_API_KEY,
            voice="Puck",
            instructions="You are a friendly voice assistant. Keep answers short and clear.",
        ),
    )

    await session.start(
        room=ctx.room,
        agent=Agent(instructions="You are a friendly voice assistant."),
    )
    await session.generate_reply(
        instructions="Greet the user and ask how you can help."
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name=AGENT_NAME))
