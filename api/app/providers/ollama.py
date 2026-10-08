"""Local models served by Ollama via the official Python SDK."""

from collections.abc import AsyncIterator

import httpx
from ollama import AsyncClient, ResponseError

from app.providers.base import Provider, ProviderError
from app.schemas import ChatMessage, ModelInfo


class OllamaProvider(Provider):
    id = "ollama"
    label = "Ollama (local)"
    local = True

    def __init__(self, host: str, enabled: bool = True, timeout: float = 120.0) -> None:
        self._host = host
        self._enabled = enabled
        self._client = AsyncClient(host=host, timeout=timeout)

    @property
    def configured(self) -> bool:
        return self._enabled and bool(self._host)

    async def list_models(self) -> list[ModelInfo]:
        try:
            response = await self._client.list()
        except (httpx.HTTPError, ConnectionError, ResponseError) as exc:
            raise ProviderError(f"Ollama is not reachable at {self._host}") from exc

        models: list[ModelInfo] = []
        for item in response.models:
            if not item.model:
                continue
            details = item.details
            # Embedding-only models cannot chat, so keep them out of the dropdown.
            families = (details.families or []) if details else []
            if any("bert" in f for f in families) or "embed" in item.model:
                continue
            models.append(
                ModelInfo(
                    id=item.model,
                    name=item.model.removesuffix(":latest"),
                    provider=self.id,
                    local=True,
                    size_bytes=item.size,
                    parameter_size=details.parameter_size if details else None,
                    family=details.family if details else None,
                )
            )
        return sorted(models, key=lambda m: m.name)

    async def stream_chat(
        self,
        model: str,
        messages: list[ChatMessage],
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        # Convert ChatMessage to Ollama format, including images.
        formatted_messages = []
        for message in messages:
            msg_dict = {"role": message.role, "content": message.content}
            if message.images:
                msg_dict["images"] = message.images
            formatted_messages.append(msg_dict)

        # Prefer the full context window. On constrained machines, a cold model
        # load may fail before producing a token; retry that allocation failure
        # with a smaller context so the local model can still answer.
        try:
            for num_ctx in (8192, 2048):
                options = {"num_ctx": num_ctx}
                if temperature is not None:
                    options["temperature"] = temperature
                started = False
                try:
                    stream = await self._client.chat(
                        model=model,
                        messages=formatted_messages,
                        stream=True,
                        options=options,
                    )
                    async for chunk in stream:
                        if chunk.message and chunk.message.content:
                            started = True
                            yield chunk.message.content
                    return
                except ResponseError as exc:
                    allocation_error = any(
                        phrase in exc.error.lower()
                        for phrase in (
                            "unable to allocate",
                            "failed to allocate",
                            "insufficient system resources",
                        )
                    )
                    if num_ctx == 8192 and not started and allocation_error:
                        continue
                    raise ProviderError(f"Ollama error: {exc.error}") from exc
        except ProviderError:
            raise
        except (httpx.HTTPError, ConnectionError) as exc:
            raise ProviderError(f"Ollama is not reachable at {self._host}") from exc
