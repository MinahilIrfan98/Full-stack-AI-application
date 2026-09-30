import jwt
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.providers.registry import ProviderRegistry


def client_for(settings: Settings) -> TestClient:
    return TestClient(create_app(settings, ProviderRegistry([], cache_ttl=0)))


def test_voice_token_requires_livekit_configuration() -> None:
    with client_for(Settings(_env_file=None)) as client:
        response = client.post("/api/voice/token")

    assert response.status_code == 503
    assert response.json()["detail"] == "LiveKit voice is not configured."


def test_voice_token_dispatches_configured_agent() -> None:
    settings = Settings(
        _env_file=None,
        livekit_url="wss://example.livekit.cloud",
        livekit_api_key="test-key",
        livekit_api_secret="test-secret-that-is-at-least-32-bytes-long",
        livekit_agent_name="assistant-agent",
    )
    with client_for(settings) as client:
        response = client.post("/api/voice/token")

    assert response.status_code == 200
    body = response.json()
    claims = jwt.decode(body["participant_token"], options={"verify_signature": False})
    assert body["server_url"] == settings.livekit_url
    assert body["room_name"].startswith("chat-")
    assert claims["video"]["room"] == body["room_name"]
    assert claims["roomConfig"]["agents"][0]["agentName"] == "assistant-agent"
