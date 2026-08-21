import asyncio

import httpx
import pytest

from app.core.config import get_settings
from app.services.embeddings import (
    EmbeddingProviderError,
    OpenRouterChatClient,
    get_draft_chat_client,
    get_reviewer_chat_client,
    get_triage_chat_client,
)


def test_openrouter_is_selected_only_when_explicitly_configured(monkeypatch) -> None:
    monkeypatch.setenv("RESOLVEAI_DRAFT_PROVIDER", "openrouter")
    monkeypatch.setenv("RESOLVEAI_OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv(
        "RESOLVEAI_OPENROUTER_DRAFT_MODEL", "openrouter/free"
    )
    get_settings.cache_clear()

    client = get_draft_chat_client()

    assert isinstance(client, OpenRouterChatClient)
    assert client.model_name == "openrouter/free"
    get_settings.cache_clear()


def test_openrouter_can_run_all_live_support_agents(monkeypatch) -> None:
    monkeypatch.setenv("RESOLVEAI_DRAFT_PROVIDER", "openrouter")
    monkeypatch.setenv("RESOLVEAI_AGENT_PROVIDER", "openrouter")
    monkeypatch.setenv("RESOLVEAI_OPENROUTER_API_KEY", "test-key")
    get_settings.cache_clear()

    assert isinstance(get_draft_chat_client(), OpenRouterChatClient)
    assert isinstance(get_triage_chat_client(), OpenRouterChatClient)
    assert isinstance(get_reviewer_chat_client(), OpenRouterChatClient)
    get_settings.cache_clear()


def test_openrouter_refuses_to_run_without_a_key(monkeypatch) -> None:
    monkeypatch.setenv("RESOLVEAI_DRAFT_PROVIDER", "openrouter")
    monkeypatch.delenv("RESOLVEAI_OPENROUTER_API_KEY", raising=False)
    get_settings.cache_clear()

    client = get_draft_chat_client()

    assert isinstance(client, OpenRouterChatClient)
    assert client.api_key is None
    with pytest.raises(EmbeddingProviderError, match="OPENROUTER_API_KEY"):
        asyncio.run(client.complete(system="system", user="user"))
    get_settings.cache_clear()


def test_openrouter_uses_the_fixed_fallback_after_a_transient_primary_failure(monkeypatch) -> None:
    monkeypatch.setenv("RESOLVEAI_OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("RESOLVEAI_OPENROUTER_DRAFT_MODEL", "primary:free")
    monkeypatch.setenv("RESOLVEAI_OPENROUTER_FALLBACK_DRAFT_MODEL", "fallback:free")
    get_settings.cache_clear()

    attempted_models: list[str] = []

    async def fake_complete_with_model(
        self: OpenRouterChatClient, model: str, system: str, user: str
    ) -> tuple[str, str]:
        attempted_models.append(model)
        if model == "primary:free":
            request = httpx.Request("POST", "https://openrouter.example/chat/completions")
            response = httpx.Response(429, request=request)
            raise httpx.HTTPStatusError("rate limited", request=request, response=response)
        return "A complete, grounded fallback draft.", model

    monkeypatch.setattr(OpenRouterChatClient, "_complete_with_model", fake_complete_with_model)
    client = OpenRouterChatClient()

    content = asyncio.run(client.complete(system="system", user="user"))

    assert content == "A complete, grounded fallback draft."
    assert attempted_models == ["primary:free", "fallback:free"]
    assert client.model_name == "fallback:free"
    assert client.last_attempts == [
        {"model": "primary:free", "outcome": "rate_limited", "status_code": 429},
        {"model": "fallback:free", "outcome": "completed", "status_code": None},
    ]
    asyncio.run(client.complete(system="system", user="another user"))
    assert attempted_models == [
        "primary:free",
        "fallback:free",
        "primary:free",
        "fallback:free",
    ]
    get_settings.cache_clear()
