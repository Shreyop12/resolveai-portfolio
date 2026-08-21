import asyncio
import re
from functools import lru_cache
from typing import Literal, Protocol

import httpx

from app.core.config import get_settings
from app.models.embedding import EMBEDDING_DIMENSIONS
from app.models.knowledge import KnowledgeArticle


class EmbeddingProviderError(RuntimeError):
    """Raised when the configured embedding model cannot produce a valid vector."""


class EmbeddingClient(Protocol):
    model_name: str

    async def embed(self, text: str) -> list[float]: ...


class ChatClient(Protocol):
    model_name: str

    async def complete(self, *, system: str, user: str) -> str: ...


class OllamaEmbeddingClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model_name = settings.ollama_embedding_model

    async def embed(self, text: str) -> list[float]:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model_name, "input": text, "truncate": False},
                )
                response.raise_for_status()
        except httpx.HTTPError as error:
            raise EmbeddingProviderError(
                "Ollama could not create an embedding. Confirm it is running and the model is installed."
            ) from error

        embeddings = response.json().get("embeddings", [])
        if not embeddings or len(embeddings[0]) != EMBEDDING_DIMENSIONS:
            raise EmbeddingProviderError(
                f"Ollama must return a {EMBEDDING_DIMENSIONS}-dimension embedding."
            )
        return [float(value) for value in embeddings[0]]


class FastEmbedEmbeddingClient:
    """Small in-process CPU embedder for cloud deployments without local Ollama."""

    def __init__(self) -> None:
        settings = get_settings()
        self.model_name = f"fastembed/{settings.fastembed_embedding_model}"
        self._fastembed_model_name = settings.fastembed_embedding_model

    async def embed(self, text: str) -> list[float]:
        try:
            embedding = await asyncio.to_thread(
                _fastembed_embed, self._fastembed_model_name, text
            )
        except Exception as error:
            raise EmbeddingProviderError(
                "FastEmbed could not create an embedding. Check that the deployment can download "
                "the configured model on first startup."
            ) from error
        if len(embedding) != EMBEDDING_DIMENSIONS:
            raise EmbeddingProviderError(
                f"FastEmbed must return a {EMBEDDING_DIMENSIONS}-dimension embedding."
            )
        return embedding


@lru_cache
def _fastembed_model(model_name: str):
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=model_name)


def _fastembed_embed(model_name: str, text: str) -> list[float]:
    embedding = next(_fastembed_model(model_name).embed([text]))
    return [float(value) for value in embedding]


def article_embedding_text(article: KnowledgeArticle) -> str:
    """Keep the article fields embedded in one visible, versioned format."""
    return f"Title: {article.title}\nCategory: {article.category}\nContent: {article.body}"


def get_embedding_client() -> EmbeddingClient:
    if get_settings().embedding_provider == "fastembed":
        return FastEmbedEmbeddingClient()
    return OllamaEmbeddingClient()


class OllamaChatClient:
    def __init__(
        self, model_name: str | None = None, max_output_tokens: int | None = None
    ) -> None:
        settings = get_settings()
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model_name = model_name or settings.ollama_chat_model
        self.timeout_seconds = settings.ollama_chat_timeout_seconds
        self.keep_alive = settings.ollama_keep_alive
        self.max_output_tokens = max_output_tokens or settings.ollama_draft_max_output_tokens

    async def complete(self, *, system: str, user: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model_name,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "stream": False,
                        "think": False,
                        "keep_alive": self.keep_alive,
                        "options": {
                            "num_predict": self.max_output_tokens,
                            "temperature": 0.2,
                        },
                    },
                )
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise EmbeddingProviderError(
                f"Ollama took longer than {self.timeout_seconds} seconds to create a draft. "
                "The service is reachable, but this local model needs more time or a smaller model."
            ) from error
        except httpx.ConnectError as error:
            raise EmbeddingProviderError(
                "ResolveAI could not reach Ollama. Confirm the Ollama app is running locally."
            ) from error
        except httpx.HTTPError as error:
            raise EmbeddingProviderError(
                "Ollama rejected the draft request. Confirm the chat model is installed and available."
            ) from error
        content = extract_customer_facing_content(
            response.json().get("message", {}).get("content", "")
        )
        if len(content) < 20:
            raise EmbeddingProviderError("Ollama returned an empty or incomplete draft.")
        return content


class OpenRouterChatClient:
    """OpenAI-compatible chat adapter used only when explicitly configured."""

    def __init__(
        self,
        *,
        model_name: str | None = None,
        use_configured_fallback: bool = True,
        timeout_seconds: float = 120,
        structured_output: Literal["none", "triage", "grounding"] = "none",
    ) -> None:
        settings = get_settings()
        self.base_url = settings.openrouter_base_url.rstrip("/")
        self.model_name = model_name or settings.openrouter_draft_model
        self.primary_model_name = self.model_name
        self.fallback_model_name = (
            settings.openrouter_fallback_draft_model if use_configured_fallback else None
        )
        self.timeout_seconds = timeout_seconds
        self.structured_output = structured_output
        self.api_key = (
            settings.openrouter_api_key.get_secret_value()
            if settings.openrouter_api_key is not None
            else None
        )
        self.last_attempts: list[dict[str, str | int | None]] = []

    async def complete(self, *, system: str, user: str) -> str:
        if not self.api_key:
            raise EmbeddingProviderError(
                "OpenRouter is selected for draft writing, but RESOLVEAI_OPENROUTER_API_KEY is not set."
            )
        self.last_attempts = []
        models = [self.primary_model_name]
        if self.fallback_model_name and self.fallback_model_name != self.primary_model_name:
            models.append(self.fallback_model_name)

        for index, model in enumerate(models):
            try:
                content, actual_model = await self._complete_with_model(model, system, user)
                self.model_name = actual_model
                self.last_attempts.append(
                    {
                        "model": actual_model,
                        "outcome": "completed",
                        "status_code": None,
                    }
                )
                return content
            except httpx.HTTPError as error:
                status_code = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
                self.last_attempts.append(
                    {
                        "model": model,
                        "outcome": "rate_limited" if status_code == 429 else "request_failed",
                        "status_code": status_code,
                    }
                )
                has_fallback = index < len(models) - 1
                if has_fallback and self._can_try_fallback(error):
                    continue
                raise EmbeddingProviderError(
                    f"OpenRouter could not create a draft. {self._attempt_summary()}"
                ) from error
            except EmbeddingProviderError as error:
                self.last_attempts.append(
                    {
                        "model": model,
                        "outcome": "incomplete_response",
                        "status_code": None,
                    }
                )
                if index < len(models) - 1:
                    continue
                raise EmbeddingProviderError(
                    f"OpenRouter could not create a complete draft. {self._attempt_summary()}"
                ) from error

        raise EmbeddingProviderError("OpenRouter could not create a draft.")

    def _attempt_summary(self) -> str:
        descriptions = []
        for attempt in self.last_attempts:
            model = str(attempt["model"])
            outcome = str(attempt["outcome"])
            status_code = attempt["status_code"]
            if outcome == "rate_limited":
                descriptions.append(f"{model} was rate limited (429)")
            elif status_code is not None:
                descriptions.append(f"{model} failed with HTTP {status_code}")
            elif outcome == "incomplete_response":
                descriptions.append(f"{model} returned an incomplete response")
            else:
                descriptions.append(f"{model} request failed")
        return "Attempts: " + "; ".join(descriptions)

    async def _complete_with_model(self, model: str, system: str, user: str) -> tuple[str, str]:
        request_body: dict[str, object] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }
        if self.structured_output != "none":
            request_body["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "http://localhost:3000",
                    "X-OpenRouter-Title": "ResolveAI",
                },
                json=request_body,
            )
            response.raise_for_status()
        payload = response.json()
        content = extract_customer_facing_content(
            payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        )
        if len(content) < 20:
            raise EmbeddingProviderError("OpenRouter returned an empty or incomplete draft.")
        return content, str(payload.get("model") or model)

    @staticmethod
    def _can_try_fallback(error: httpx.HTTPError) -> bool:
        if isinstance(error, httpx.HTTPStatusError):
            status_code = error.response.status_code
            return status_code == 408 or status_code == 429 or status_code >= 500
        return isinstance(error, (httpx.ConnectError, httpx.TimeoutException))


class GeminiChatClient:
    """Direct Gemini adapter. The API key is read only by this backend process."""

    def __init__(
        self,
        *,
        model_name: str | None = None,
        timeout_seconds: float | None = None,
        structured_output: Literal["none", "triage", "grounding"] = "none",
    ) -> None:
        settings = get_settings()
        self.base_url = settings.gemini_base_url.rstrip("/")
        self.model_name = model_name or settings.gemini_model
        self.timeout_seconds = timeout_seconds or settings.gemini_timeout_seconds
        self.structured_output = structured_output
        self.api_key = (
            settings.gemini_api_key.get_secret_value()
            if settings.gemini_api_key is not None
            else None
        )
        self.last_attempts: list[dict[str, str | int | None]] = []

    async def complete(self, *, system: str, user: str) -> str:
        if not self.api_key:
            raise EmbeddingProviderError(
                "Gemini is selected for support generation, but RESOLVEAI_GEMINI_API_KEY is not set."
            )

        generation_config: dict[str, object] = {"temperature": 0.2}
        schema = self._structured_schema()
        if schema is not None:
            generation_config["responseFormat"] = {
                "text": {"mimeType": "application/json", "schema": schema}
            }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/models/{self.model_name}:generateContent",
                    headers={"x-goog-api-key": self.api_key},
                    json={
                        "systemInstruction": {"parts": [{"text": system}]},
                        "contents": [{"role": "user", "parts": [{"text": user}]}],
                        "generationConfig": generation_config,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as error:
            status_code = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
            self.last_attempts = [
                {
                    "provider": "gemini",
                    "model": self.model_name,
                    "outcome": "rate_limited" if status_code == 429 else "request_failed",
                    "status_code": status_code,
                }
            ]
            raise EmbeddingProviderError(self._error_message(status_code)) from error

        content = extract_customer_facing_content(self._response_text(response.json()))
        if len(content) < 20:
            self.last_attempts = [
                {
                    "provider": "gemini",
                    "model": self.model_name,
                    "outcome": "incomplete_response",
                    "status_code": None,
                }
            ]
            raise EmbeddingProviderError("Gemini returned an empty or incomplete response.")
        self.last_attempts = [
            {
                "provider": "gemini",
                "model": self.model_name,
                "outcome": "completed",
                "status_code": None,
            }
        ]
        return content

    def _structured_schema(self) -> dict[str, object] | None:
        if self.structured_output == "triage":
            return {
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                        "enum": ["draft_allowed", "human_escalation"],
                    },
                    "category": {
                        "type": "string",
                        "enum": [
                            "troubleshooting",
                            "how_to",
                            "account_or_billing",
                            "security_or_privacy",
                            "uncertain",
                        ],
                    },
                    "reason": {"type": "string"},
                },
                "required": ["decision", "category", "reason"],
            }
        if self.structured_output == "grounding":
            return {
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                        "enum": ["grounded", "needs_human_review"],
                    },
                    "reason": {"type": "string"},
                },
                "required": ["decision", "reason"],
            }
        return None

    @staticmethod
    def _response_text(payload: dict[str, object]) -> str:
        candidates = payload.get("candidates", [])
        if not isinstance(candidates, list) or not candidates:
            return ""
        candidate = candidates[0]
        if not isinstance(candidate, dict):
            return ""
        content = candidate.get("content", {})
        if not isinstance(content, dict):
            return ""
        parts = content.get("parts", [])
        if not isinstance(parts, list):
            return ""
        return "".join(
            part.get("text", "") for part in parts if isinstance(part, dict)
        )

    def _error_message(self, status_code: int | None) -> str:
        if status_code == 429:
            return "Gemini is temporarily rate limited."
        if status_code is not None:
            return f"Gemini rejected the support-generation request (HTTP {status_code})."
        return "Gemini could not be reached for support generation."


class FallbackChatClient:
    """Try an independent hosted provider only after the configured primary fails."""

    def __init__(self, primary: ChatClient, fallback: ChatClient) -> None:
        self.primary = primary
        self.fallback = fallback
        self.model_name = primary.model_name
        self.last_attempts: list[dict[str, str | int | None]] = []

    async def complete(self, *, system: str, user: str) -> str:
        try:
            content = await self.primary.complete(system=system, user=user)
            self.model_name = self.primary.model_name
            self.last_attempts = list(getattr(self.primary, "last_attempts", []))
            return content
        except EmbeddingProviderError as primary_error:
            primary_attempts = list(getattr(self.primary, "last_attempts", []))
            try:
                content = await self.fallback.complete(system=system, user=user)
            except EmbeddingProviderError as fallback_error:
                fallback_attempts = list(getattr(self.fallback, "last_attempts", []))
                self.last_attempts = primary_attempts + fallback_attempts
                raise EmbeddingProviderError(
                    "The primary Gemini provider and the OpenRouter fallback both failed. "
                    f"Gemini: {primary_error}. OpenRouter: {fallback_error}."
                ) from fallback_error
            self.model_name = self.fallback.model_name
            self.last_attempts = primary_attempts + list(
                getattr(self.fallback, "last_attempts", [])
            )
            return content


def _gemini_with_openrouter_fallback(
    *,
    structured_output: Literal["none", "triage", "grounding"] = "none",
    timeout_seconds: float | None = None,
) -> ChatClient:
    settings = get_settings()
    return FallbackChatClient(
        GeminiChatClient(
            timeout_seconds=timeout_seconds,
            structured_output=structured_output,
        ),
        OpenRouterChatClient(
            timeout_seconds=timeout_seconds or 120,
            structured_output=structured_output,
        ),
    )


def get_triage_chat_client() -> ChatClient:
    settings = get_settings()
    if settings.agent_provider == "gemini":
        return _gemini_with_openrouter_fallback(
            structured_output="triage", timeout_seconds=settings.openrouter_agent_timeout_seconds
        )
    if settings.agent_provider == "openrouter":
        return OpenRouterChatClient(
            timeout_seconds=settings.openrouter_agent_timeout_seconds,
            structured_output="triage",
        )
    return OllamaChatClient(
        settings.ollama_triage_model, settings.ollama_triage_max_output_tokens
    )


def get_reviewer_chat_client() -> ChatClient:
    settings = get_settings()
    if settings.agent_provider == "gemini":
        return _gemini_with_openrouter_fallback(
            structured_output="grounding", timeout_seconds=settings.openrouter_agent_timeout_seconds
        )
    if settings.agent_provider == "openrouter":
        return OpenRouterChatClient(
            timeout_seconds=settings.openrouter_agent_timeout_seconds,
            structured_output="grounding",
        )
    return OllamaChatClient(
        settings.ollama_reviewer_model, settings.ollama_reviewer_max_output_tokens
    )


def get_ollama_draft_chat_client() -> ChatClient:
    return OllamaChatClient(get_settings().ollama_chat_model)


def get_openrouter_draft_chat_client() -> ChatClient:
    return OpenRouterChatClient()


def get_draft_chat_client() -> ChatClient:
    settings = get_settings()
    if settings.draft_provider == "gemini":
        return _gemini_with_openrouter_fallback()
    if settings.draft_provider == "openrouter":
        return get_openrouter_draft_chat_client()
    return get_ollama_draft_chat_client()


def get_chat_client() -> ChatClient:
    """Compatibility alias for the draft-writer client dependency."""
    return get_draft_chat_client()


def extract_customer_facing_content(content: str) -> str:
    """Discard reasoning blocks even if a local model emits them in content."""
    if "</think>" in content.lower():
        content = re.split(r"</think>", content, flags=re.IGNORECASE)[-1]
    return re.sub(r"<think>.*?</think>", "", content, flags=re.IGNORECASE | re.DOTALL).strip()
