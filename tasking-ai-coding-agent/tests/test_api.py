"""
Integration tests for the FastAPI task endpoints.
Uses an in-memory SQLite DB and mocks Celery.
"""
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.database import get_db
from app.models import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


# ─── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.anyio
@patch("app.api.tasks.run_coding_pipeline")
async def test_create_task(mock_celery, client):
    mock_celery.delay.return_value = MagicMock(id="fake-celery-id")
    payload = {"title": "Build a calculator", "description": "Write a Python calculator with add/sub/mul/div operations."}
    r = await client.post("/api/tasks/", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["title"] == "Build a calculator"
    assert data["status"] == "pending"


@pytest.mark.anyio
@patch("app.api.tasks.run_coding_pipeline")
async def test_list_tasks(mock_celery, client):
    mock_celery.delay.return_value = MagicMock(id="fake-id")
    await client.post("/api/tasks/", json={"title": "Task A", "description": "Description for task A is long enough."})
    r = await client.get("/api/tasks/")
    assert r.status_code == 200
    assert len(r.json()) == 1


@pytest.mark.anyio
@patch("app.api.tasks.run_coding_pipeline")
async def test_get_task_not_found(mock_celery, client):
    r = await client.get("/api/tasks/nonexistent-id")
    assert r.status_code == 404


@pytest.mark.anyio
@patch("app.api.tasks.run_coding_pipeline")
async def test_create_task_validation(mock_celery, client):
    # Too short description
    r = await client.post("/api/tasks/", json={"title": "X", "description": "short"})
    assert r.status_code == 422
