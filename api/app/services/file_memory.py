"""In-memory chunk storage and Ollama vector retrieval for uploaded documents."""

import asyncio
import logging
import math
import uuid
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 120
MAX_CHUNKS_PER_SESSION = 50_000


@dataclass(frozen=True)
class DocumentChunk:
    text: str
    embedding: list[float]


@dataclass
class StoredDocument:
    filename: str
    chunks: list[DocumentChunk]


class FileMemory:
    def __init__(self, ollama_host: str) -> None:
        self._host = ollama_host.rstrip("/")
        self._documents: dict[str, StoredDocument] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _split(text: str) -> list[str]:
        if not text:
            return []
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start = end - CHUNK_OVERLAP
        return chunks

    async def _embed(self, client: httpx.AsyncClient, text: str) -> list[float]:
        response = await client.post(
            f"{self._host}/api/embed",
            json={"model": EMBED_MODEL, "input": text},
        )
        if response.status_code == 404:
            raise httpx.HTTPStatusError(
                f"Ollama embedding model '{EMBED_MODEL}' is missing.",
                request=response.request,
                response=response,
            )
        response.raise_for_status()
        body = response.json()
        embeddings = body.get("embeddings") or []
        if not embeddings:
            raise RuntimeError("Ollama returned no embedding for the uploaded document.")
        return embeddings[0]

    async def _ensure_model(self, client: httpx.AsyncClient) -> None:
        response = await client.post(
            f"{self._host}/api/pull",
            json={"name": EMBED_MODEL, "stream": False},
            timeout=None,
        )
        response.raise_for_status()

    async def index(self, filename: str, text: str) -> str:
        session_id = str(uuid.uuid4())
        chunks = self._split(text)
        if len(chunks) > MAX_CHUNKS_PER_SESSION:
            raise ValueError("File contains too many chunks to index in memory.")

        timeout = httpx.Timeout(600.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                embedded = []
                for start in range(0, len(chunks), 16):
                    embedded.extend(
                        await asyncio.gather(
                            *(self._embed(client, chunk) for chunk in chunks[start : start + 16])
                        )
                    )
            except RuntimeError as exc:
                if EMBED_MODEL in str(exc):
                    await self._ensure_model(client)
                    embedded = []
                    for start in range(0, len(chunks), 16):
                        embedded.extend(
                            await asyncio.gather(
                                *(
                                    self._embed(client, chunk)
                                    for chunk in chunks[start : start + 16]
                                )
                            )
                        )
                else:
                    raise
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    await self._ensure_model(client)
                    embedded = []
                    for start in range(0, len(chunks), 16):
                        embedded.extend(
                            await asyncio.gather(
                                *(
                                    self._embed(client, chunk)
                                    for chunk in chunks[start : start + 16]
                                )
                            )
                        )
                else:
                    raise
            except Exception as exc:
                if "not found" not in str(exc).lower() or EMBED_MODEL not in str(exc):
                    raise
                await self._ensure_model(client)
                embedded = []
                for start in range(0, len(chunks), 16):
                    embedded.extend(
                        await asyncio.gather(
                            *(self._embed(client, chunk) for chunk in chunks[start : start + 16])
                        )
                    )

        async with self._lock:
            self._documents[session_id] = StoredDocument(
                filename=filename,
                chunks=[DocumentChunk(chunk, vector) for chunk, vector in zip(chunks, embedded)],
            )
        return session_id

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if not left_norm or not right_norm:
            return 0.0
        return dot / (left_norm * right_norm)

    async def search(self, session_id: str, query: str, top_k: int = 5) -> list[str]:
        async with self._lock:
            document = self._documents.get(session_id)
        if not document:
            raise KeyError("Uploaded file context expired. Please attach the file again.")
        async with httpx.AsyncClient(timeout=60.0) as client:
            query_embedding = await self._embed(client, query)
        ranked = sorted(
            document.chunks,
            key=lambda chunk: self._cosine(query_embedding, chunk.embedding),
            reverse=True,
        )
        return [chunk.text for chunk in ranked[:top_k]]


_instances: dict[str, FileMemory] = {}


def get_file_memory(ollama_host: str) -> FileMemory:
    instance = _instances.get(ollama_host)
    if instance is None:
        instance = FileMemory(ollama_host)
        _instances[ollama_host] = instance
    return instance
