from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="RESOLVEAI_", extra="ignore"
    )

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://resolveai:resolveai@localhost:5432/resolveai"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"
    ollama_base_url: str = "http://localhost:11434"
    ollama_embedding_model: str = "embeddinggemma"
    embedding_provider: Literal["ollama", "fastembed"] = "ollama"
    fastembed_embedding_model: str = "nomic-ai/nomic-embed-text-v1.5-Q"
    ollama_chat_model: str = "qwen3:4b"
    ollama_chat_timeout_seconds: int = 300
    ollama_keep_alive: str = "15m"
    ollama_draft_max_output_tokens: int = Field(default=220, ge=20, le=1_000)
    ollama_triage_model: str = "qwen3:4b"
    ollama_triage_max_output_tokens: int = Field(default=80, ge=20, le=500)
    ollama_reviewer_model: str = "qwen3:4b"
    ollama_reviewer_max_output_tokens: int = Field(default=80, ge=20, le=500)
    draft_min_semantic_similarity: float = Field(default=0.55, ge=0.0, le=1.0)
    draft_provider: Literal["ollama", "openrouter"] = "ollama"
    agent_provider: Literal["ollama", "openrouter"] = "ollama"
    draft_evaluation_execution_mode: Literal["redis", "database", "inline"] = "redis"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: SecretStr | None = None
    openrouter_draft_model: str = "openai/gpt-oss-20b:free"
    openrouter_fallback_draft_model: str | None = "z-ai/glm-5.2:free"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_postgres_url_for_async_driver(cls, value: object) -> object:
        """Accept managed-Postgres URLs while using SQLAlchemy's async driver."""
        if not isinstance(value, str):
            return value
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def migration_database_url(self) -> str:
        """Return the synchronous URL required by Alembic migrations."""
        return self.database_url.replace("postgresql+asyncpg", "postgresql+psycopg")


@lru_cache
def get_settings() -> Settings:
    return Settings()
