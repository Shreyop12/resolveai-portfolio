from app.core.config import Settings


def test_standard_postgres_url_uses_async_driver() -> None:
    settings = Settings(database_url="postgresql://user:password@db.example:5432/resolveai")

    assert settings.database_url == "postgresql+asyncpg://user:password@db.example:5432/resolveai"
    assert settings.migration_database_url == "postgresql+psycopg://user:password@db.example:5432/resolveai"


def test_postgres_shorthand_uses_async_driver() -> None:
    settings = Settings(database_url="postgres://user:password@db.example:5432/resolveai")

    assert settings.database_url == "postgresql+asyncpg://user:password@db.example:5432/resolveai"
