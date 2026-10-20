"""Persistent document chunk storage and Ollama vector retrieval."""

import logging
import math
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)
EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
EMBED_BATCH_SIZE = 32
MAX_CHUNKS_PER_FILE = 50_000


@dataclass(frozen=True)
class SearchResult:
    file_id: str
    filename: str
    chunk_index: int
    text: str
    score: float


class FileMemory:
    def __init__(self, ollama_host: str, settings: Settings | None = None) -> None:
        settings = settings or Settings(_env_file=None)
        self._host = ollama_host.rstrip("/")
        self._size = settings.rag_chunk_size
        self._overlap = settings.rag_chunk_overlap
        if self._size <= 0 or self._overlap < 0 or self._overlap >= self._size:
            raise ValueError(
                "RAG_CHUNK_SIZE must be positive and RAG_CHUNK_OVERLAP must be smaller."
            )
        self._top_k = settings.rag_top_k
        self._min_score = settings.rag_min_score
        self._path = Path(settings.rag_data_dir)
        self._path.mkdir(parents=True, exist_ok=True)
        self._db = self._path / "index.sqlite3"
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("PRAGMA foreign_keys = ON")
            db.execute(
                "CREATE TABLE IF NOT EXISTS files (id TEXT PRIMARY KEY, filename TEXT NOT NULL)"
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS chunks (
                    file_id TEXT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    PRIMARY KEY (file_id, chunk_index)
                )"""
            )

    @staticmethod
    def _normalize(vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    def _split(self, text: str) -> list[str]:
        if not text:
            return []
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + self._size, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start = end - self._overlap
        return chunks

    async def _embed_batch(
        self, client: httpx.AsyncClient, texts: list[str], prefix: str
    ) -> list[list[float]]:
        response = await client.post(
            f"{self._host}/api/embed",
            json={"model": EMBED_MODEL, "input": [f"{prefix}{text}" for text in texts]},
        )
        if response.status_code == 404:
            raise RuntimeError(
                f"Ollama embedding model '{EMBED_MODEL}' is missing. Run `ollama pull {EMBED_MODEL}`."
            )
        response.raise_for_status()
        body = response.json()
        vectors = body.get("embeddings") or ([body["embedding"]] if "embedding" in body else [])
        if len(vectors) != len(texts):
            raise RuntimeError("Ollama returned an invalid number of embeddings.")
        return [self._normalize(vector) for vector in vectors]

    async def _embed_all(self, texts: list[str], prefix: str) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=600.0) as client:
            vectors = []
            for start in range(0, len(texts), EMBED_BATCH_SIZE):
                vectors.extend(
                    await self._embed_batch(client, texts[start : start + EMBED_BATCH_SIZE], prefix)
                )
            return vectors

    async def index(self, filename: str, text: str) -> str:
        chunks = self._split(text)
        if len(chunks) > MAX_CHUNKS_PER_FILE:
            raise ValueError("File contains too many chunks to index.")
        if not chunks:
            raise ValueError("No text could be extracted from this file.")
        vectors = await self._embed_all(chunks, "search_document: ")
        file_id = str(uuid.uuid4())
        with self._connect() as db:
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("INSERT INTO files (id, filename) VALUES (?, ?)", (file_id, filename))
            db.executemany(
                "INSERT INTO chunks (file_id, chunk_index, text, embedding) VALUES (?, ?, ?, ?)",
                [
                    (file_id, index, chunk, sqlite3.Binary(_encode(vector)))
                    for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
                ],
            )
        return file_id

    async def search(
        self, file_ids: list[str], query: str, top_k: int | None = None
    ) -> list[SearchResult]:
        if not file_ids:
            return []
        (query_vector,) = await self._embed_all([query], "search_query: ")
        placeholders = ",".join("?" for _ in file_ids)
        with self._connect() as db:
            rows = db.execute(
                f"""SELECT chunks.file_id, files.filename, chunks.chunk_index,
                           chunks.text, chunks.embedding FROM chunks
                    JOIN files ON files.id = chunks.file_id
                    WHERE chunks.file_id IN ({placeholders})""",
                file_ids,
            ).fetchall()
        ranked = []
        for row in rows:
            embedding = _decode(row["embedding"])
            if len(query_vector) != len(embedding):
                logger.warning("Skipping stored chunk with an incompatible embedding dimension")
                continue
            score = sum(left * right for left, right in zip(query_vector, embedding, strict=True))
            if score >= self._min_score:
                ranked.append(
                    SearchResult(
                        row["file_id"], row["filename"], row["chunk_index"], row["text"], score
                    )
                )
        limit = self._top_k if top_k is None else top_k
        return sorted(ranked, key=lambda item: item.score, reverse=True)[:limit]

    async def delete(self, file_id: str) -> bool:
        with self._connect() as db:
            db.execute("PRAGMA foreign_keys = ON")
            cursor = db.execute("DELETE FROM files WHERE id = ?", (file_id,))
            return cursor.rowcount > 0


def _encode(vector: list[float]) -> bytes:
    import array

    values = array.array("f", vector)
    return values.tobytes()


def _decode(blob: bytes) -> list[float]:
    import array

    values = array.array("f")
    values.frombytes(blob)
    return list(values)


_instances: dict[tuple[str, str], FileMemory] = {}


def get_file_memory(ollama_host: str, settings: Settings | None = None) -> FileMemory:
    config = settings or Settings(_env_file=None)
    key = (ollama_host, config.rag_data_dir)
    instance = _instances.get(key)
    if instance is None:
        instance = FileMemory(ollama_host, config)
        _instances[key] = instance
    return instance
