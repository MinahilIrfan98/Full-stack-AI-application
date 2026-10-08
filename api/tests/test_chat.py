from tests.conftest import FakeProvider, parse_sse
from app.services.file_memory import FileMemory

USER = {"messages": [{"role": "user", "content": "Hi"}]}


def text_of(events):
    return "".join(d["delta"] for name, d in events if name == "message")


def test_streams_from_local_model_by_default(make_client):
    ollama = FakeProvider("ollama", local=True, models=["llama3.2"], reply="Hi from local")
    cloud = FakeProvider("openai", models=["gpt-x"], reply="Hi from cloud")
    client = make_client(ollama, cloud)

    res = client.post("/api/chat", json=USER)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(res.text)

    assert events[0] == (
        "meta",
        {
            "provider": "ollama",
            "provider_label": "Ollama",
            "model": "llama3.2",
            "local": True,
            "fallback": False,
            "notice": None,
        },
    )
    assert text_of(events) == "Hi from local"
    assert events[-1] == ("done", {})
    assert cloud.calls == []


def test_system_prompt_is_prepended(make_client):
    ollama = FakeProvider("ollama", local=True, models=["m"])
    make_client(ollama).post("/api/chat", json=USER)
    _, messages = ollama.calls[0]
    assert messages[0].role == "system"
    assert messages[0].content == "Be helpful."


def test_file_context_is_added_to_last_user_prompt(make_client):
    ollama = FakeProvider("ollama", local=True, models=["gemma3:1b"])
    client = make_client(ollama)

    response = client.post(
        "/api/chat",
        json={
            "messages": [{"role": "user", "content": "Repeat the phrase."}],
            "provider": "ollama",
            "model": "gemma3:1b",
            "file_context": {"filename": "test.txt", "text": "phrase: upload-chain-7f3a"},
        },
    )

    assert response.status_code == 200
    _, messages = ollama.calls[0]
    assert messages[-1].content == (
        "Context from test.txt:\n"
        "phrase: upload-chain-7f3a\n\n"
        "User Question: Repeat the phrase."
    )


async def test_large_file_context_retrieves_only_matching_chunks(make_client, monkeypatch):
    ollama = FakeProvider("ollama", local=True, models=["gemma3:1b"])
    memory = FileMemory("http://localhost:11434")

    async def search(session_id, query, top_k=5):
        assert session_id == "session-1"
        assert query == "What was the key result?"
        assert top_k == 5
        return ["Key result: 42 participants improved."]

    monkeypatch.setattr(memory, "search", search)
    monkeypatch.setattr("app.services.chat.get_file_memory", lambda host: memory)
    response = make_client(ollama).post(
        "/api/chat",
        json={
            "messages": [{"role": "user", "content": "What was the key result?"}],
            "file_context": {
                "filename": "study.pdf",
                "session_id": "session-1",
                "retrieval": True,
            },
        },
    )

    assert response.status_code == 200
    _, messages = ollama.calls[0]
    assert "Key result: 42 participants improved." in messages[-1].content
    assert "session-1" not in messages[-1].content


def test_uses_explicitly_selected_model(make_client):
    ollama = FakeProvider("ollama", local=True, models=["a", "b"])
    cloud = FakeProvider("openai", models=["gpt-x", "gpt-y"], reply="cloud")
    client = make_client(ollama, cloud)

    events = parse_sse(
        client.post("/api/chat", json={**USER, "provider": "openai", "model": "gpt-y"}).text
    )
    assert events[0][1]["provider"] == "openai"
    assert events[0][1]["model"] == "gpt-y"
    assert ollama.calls == []


def test_falls_back_to_cloud_when_no_local_models(make_client):
    ollama = FakeProvider("ollama", local=True, list_error="Ollama is not reachable")
    cloud = FakeProvider("anthropic", models=["claude"], reply="Cloud answer")
    events = parse_sse(make_client(ollama, cloud).post("/api/chat", json=USER).text)

    assert events[0][1]["provider"] == "anthropic"
    assert text_of(events) == "Cloud answer"


def test_falls_back_when_selected_model_fails_before_first_token(make_client):
    ollama = FakeProvider("ollama", local=True, models=["m"], chat_error="model not found")
    cloud = FakeProvider("openai", models=["gpt-x"], reply="Recovered")
    events = parse_sse(
        make_client(ollama, cloud)
        .post("/api/chat", json={**USER, "provider": "ollama", "model": "m"})
        .text
    )

    meta = events[0][1]
    assert meta["provider"] == "openai"
    assert meta["fallback"] is True
    assert "model not found" in meta["notice"]
    assert text_of(events) == "Recovered"


def test_no_fallback_when_disabled(make_client):
    ollama = FakeProvider("ollama", local=True, models=["m"], chat_error="boom")
    cloud = FakeProvider("openai", models=["gpt-x"])
    client = make_client(ollama, cloud, allow_cloud_fallback=False)
    events = parse_sse(client.post("/api/chat", json=USER).text)

    assert events == [("error", {"message": "boom"})]
    assert cloud.calls == []


def test_mid_stream_failure_reports_error_without_switching(make_client):
    ollama = FakeProvider(
        "ollama", local=True, models=["m"], reply="one two three", fail_after_tokens=2
    )
    cloud = FakeProvider("openai", models=["gpt-x"])
    events = parse_sse(make_client(ollama, cloud).post("/api/chat", json=USER).text)

    assert text_of(events) == "one two"
    assert events[-1] == ("error", {"message": "connection dropped"})
    assert cloud.calls == []


def test_helpful_error_when_nothing_is_available(make_client):
    client = make_client(
        FakeProvider("ollama", local=True, models=[]),
        FakeProvider("openai", configured=False),
    )
    events = parse_sse(client.post("/api/chat", json=USER).text)
    assert events[0][0] == "error"
    assert "ollama pull" in events[0][1]["message"]


def test_unknown_provider_is_an_error_event(make_client):
    client = make_client(FakeProvider("ollama", local=True, models=["m"]))
    events = parse_sse(client.post("/api/chat", json={**USER, "provider": "nope"}).text)
    assert events == [("error", {"message": "Unknown provider 'nope'"})]


def test_validation(make_client):
    client = make_client(FakeProvider("ollama", local=True, models=["m"]))
    assert client.post("/api/chat", json={"messages": []}).status_code == 422
    assert (
        client.post(
            "/api/chat", json={"messages": [{"role": "assistant", "content": "x"}]}
        ).status_code
        == 422
    )
    assert (
        client.post("/api/chat", json={"messages": [{"role": "tool", "content": "x"}]}).status_code
        == 422
    )
