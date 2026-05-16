from __future__ import annotations

import os
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[1]
LOGIC_CORE = ROOT / "docs" / "03_Logic_Core"
TEST_DATABASE_PATH = ROOT / ".pytest_sgs_sentinel.db"

if str(LOGIC_CORE) not in sys.path:
    sys.path.insert(0, str(LOGIC_CORE))

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["SECRET_KEY"] = "pytest-secret-key"
os.environ["SGS_DEVICE_ID"] = "pytest-device-0001"
os.environ["STRICT_DATABASE_URL"] = "false"

from app.database import AsyncSessionLocal, engine, get_db
from app.main import app
from app.models import Base


@pytest_asyncio.fixture(autouse=True)
async def reset_test_database() -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[object, None]:
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        async with AsyncSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(scope="session", autouse=True)
def _cleanup_database_file() -> None:
    yield
    if TEST_DATABASE_PATH.exists():
        TEST_DATABASE_PATH.unlink()