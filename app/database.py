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

# Use environment DATABASE_URL or fall back to SQLite for local development
try:
    database_url = settings.DATABASE_URL or os.getenv("DATABASE_URL", "sqlite:///./test.db")
    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
except Exception as e:
    # Fallback: always use SQLite if connection fails
    print(f"Database connection warning: {e}. Using SQLite fallback.")
    engine = create_async_engine("sqlite:///./test.db", echo=False, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""

    async with AsyncSessionLocal() as session:
        yield session