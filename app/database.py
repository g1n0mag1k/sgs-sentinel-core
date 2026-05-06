from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    DATABASE_URL: str | None = None
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()


def normalize_database_url(raw_url: str) -> str:
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    if raw_url.startswith("postgresql://") and "+asyncpg" not in raw_url:
        return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw_url.startswith("sqlite://") and "+aiosqlite" not in raw_url:
        return raw_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return raw_url


# Use environment DATABASE_URL or fall back to SQLite for local development
raw_database_url = settings.DATABASE_URL or os.getenv("DATABASE_URL")
database_url = normalize_database_url(raw_database_url) if raw_database_url else "sqlite+aiosqlite:///./test.db"
try:
    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
except Exception as exc:
    # Fallback to SQLite when DATABASE_URL is missing or invalid.
    print(f"Database connection warning: {exc}. Using SQLite fallback.")
    engine = create_async_engine("sqlite+aiosqlite:///./test.db", echo=False, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""

    async with AsyncSessionLocal() as session:
        yield session