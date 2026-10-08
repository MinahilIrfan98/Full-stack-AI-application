from app.middleware.upload_limit import UploadLimitMiddleware
from app.routes.upload import MAX_TEXT_LENGTH
from app.services.file_memory import CHUNK_OVERLAP, CHUNK_SIZE, FileMemory


def test_file_memory_splits_with_small_overlap():
    text = "a" * (CHUNK_SIZE + 50)
    chunks = FileMemory._split(text)

    assert len(chunks) == 2
    assert len(chunks[0]) == CHUNK_SIZE
    assert chunks[0][-CHUNK_OVERLAP:] == chunks[1][:CHUNK_OVERLAP]


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


def test_small_file_text_limit_stays_8000():
    assert MAX_TEXT_LENGTH == 8000
