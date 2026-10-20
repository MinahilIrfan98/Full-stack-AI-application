import pytest

from app.core.config import Settings

from app.middleware.upload_limit import UploadLimitMiddleware
from app.services.file_memory import CHUNK_OVERLAP, CHUNK_SIZE, FileMemory


def test_file_memory_splits_with_small_overlap():
    text = "a" * (CHUNK_SIZE + 50)
    chunks = FileMemory._split(text)

    assert len(chunks) == 2
    assert len(chunks[0]) == CHUNK_SIZE
    assert chunks[0][-CHUNK_OVERLAP:] == chunks[1][:CHUNK_OVERLAP]


async def test_search_ranks_normalized_embeddings_and_applies_threshold(tmp_path, monkeypatch):
    memory = FileMemory(
        "http://localhost:11434",
        Settings(_env_file=None, rag_data_dir=str(tmp_path), rag_min_score=0.75),
    )
    vectors = [[1.0, 0.0], [0.0, 1.0]]

    async def embed_all(texts, prefix):
        assert prefix in {"search_document: ", "search_query: "}
        if prefix == "search_document: ":
            return vectors
        return [[1.0, 0.0]]

    monkeypatch.setattr(memory, "_embed_all", embed_all)
    file_id = await memory.index("notes.txt", "first " * 1000)
    results = await memory.search([file_id], "question")

    assert len(results) == 1
    assert results[0].chunk_index == 0
    assert results[0].score == pytest.approx(1.0)


async def test_index_persists_across_service_instances(tmp_path, monkeypatch):
    settings = Settings(_env_file=None, rag_data_dir=str(tmp_path))
    first = FileMemory("http://localhost:11434", settings)

    async def embed_all(texts, prefix):
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(first, "_embed_all", embed_all)
    file_id = await first.index("persistent.md", "durable text")
    second = FileMemory("http://localhost:11434", settings)
    monkeypatch.setattr(second, "_embed_all", embed_all)
    results = await second.search([file_id], "durable")

    assert results[0].filename == "persistent.md"
    assert results[0].text == "durable text"


async def test_embedding_requests_are_batched_and_prefixed(tmp_path, monkeypatch):
    memory = FileMemory(
        "http://localhost:11434", Settings(_env_file=None, rag_data_dir=str(tmp_path))
    )
    requests = []

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"embeddings": [[3.0, 4.0]] * len(requests[-1]["input"])}

        @staticmethod
        def raise_for_status():
            return None

    class Client:
        async def post(self, url, json):
            assert url.endswith("/api/embed")
            requests.append(json)
            return Response()

    vectors = await memory._embed_batch(Client(), ["one", "two"], "search_document: ")

    assert requests[0]["model"] == "nomic-embed-text"
    assert requests[0]["input"] == ["search_document: one", "search_document: two"]
    assert vectors[0] == pytest.approx([0.6, 0.8])


async def test_upload_route_rejects_file_over_configured_limit(make_client):
    from tests.conftest import FakeProvider

    client = make_client(FakeProvider("ollama", local=True), max_upload_mb=1)
    response = client.post(
        "/api/upload",
        files={"file": ("oversized.txt", b"a" * (1024 * 1024 + 1), "text/plain")},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "File is too large, max 1 MB"


def test_upload_limit_middleware_rejects_large_content_length():
    sent = []

    async def app(scope, receive, send):
        raise AssertionError("The request should be rejected before app parsing")

    middleware = UploadLimitMiddleware(app, max_upload_bytes=4 * 1024 * 1024)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/upload",
        "headers": [(b"content-length", str(24 * 1024 * 1024).encode())],
    }

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        sent.append(message)

    import asyncio

    asyncio.run(middleware(scope, receive, send))
    assert sent[0]["status"] == 413
    assert b"File is too large, max 4 MB" in sent[1]["body"]


async def test_upload_returns_file_id(make_client, monkeypatch, tmp_path):
    from tests.conftest import FakeProvider

    async def index(filename, text):
        assert filename == "note.txt"
        assert text == "some content"
        return "stable-id"

    async def delete(file_id):
        return file_id == "stable-id"

    memory = FileMemory(
        "http://localhost:11434", Settings(_env_file=None, rag_data_dir=str(tmp_path))
    )
    monkeypatch.setattr(memory, "index", index)
    monkeypatch.setattr(memory, "delete", delete)
    monkeypatch.setattr("app.routes.upload.get_file_memory", lambda host, settings: memory)
    client = make_client(FakeProvider("ollama", local=True), rag_data_dir=str(tmp_path))
    response = client.post("/api/upload", files={"file": ("note.txt", b"some content", "text/plain")})

    assert response.status_code == 200
    assert response.json()["file_id"] == "stable-id"
    assert response.json()["filename"] == "note.txt"
    assert client.delete("/api/upload/stable-id").status_code == 204
