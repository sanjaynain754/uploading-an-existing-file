import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.api import tasks, approvals
from app.config import get_settings

log = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup.init_db")
    await init_db()
    log.info("startup.ready")
    yield
    log.info("shutdown")


app = FastAPI(
    title="AI Coding Agent",
    description="Submit coding tasks to an LLM-powered agent that plans, codes, scans, tests, and raises PRs.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router)
app.include_router(approvals.router)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "env": settings.app_env}
