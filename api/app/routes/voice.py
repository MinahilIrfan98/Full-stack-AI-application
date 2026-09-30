"""LiveKit credentials for browser voice sessions."""

from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from livekit import api
from pydantic import BaseModel

from app.deps import SettingsDep

router = APIRouter(tags=["voice"])


class VoiceTokenResponse(BaseModel):
    server_url: str
    participant_token: str
    room_name: str


@router.post("/voice/token", response_model=VoiceTokenResponse)
async def create_voice_token(settings: SettingsDep) -> VoiceTokenResponse:
    """Create a short-lived, room-scoped token and dispatch the configured agent."""
    secret = settings.livekit_api_secret
    configured = (
        settings.livekit_url,
        settings.livekit_api_key,
        secret,
        settings.livekit_agent_name,
    )
    if not all(configured):
        raise HTTPException(status_code=503, detail="LiveKit voice is not configured.")

    room_name = f"chat-{uuid4().hex}"
    identity = f"user-{uuid4().hex}"
    token = (
        api.AccessToken(settings.livekit_api_key, secret.get_secret_value())
        .with_identity(identity)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
        .with_room_config(
            api.RoomConfiguration(
                agents=[api.RoomAgentDispatch(agent_name=settings.livekit_agent_name)]
            )
        )
        .with_ttl(timedelta(minutes=10))
        .to_jwt()
    )
    return VoiceTokenResponse(
        server_url=settings.livekit_url,
        participant_token=token,
        room_name=room_name,
    )
