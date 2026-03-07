"""
Celery task definitions. These are the entry points for background work.
Uses a synchronous SQLAlchemy session (not async) since Celery workers are sync.
"""
from __future__ import annotations
import structlog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.workers.celery_app import celery_app
from app.config import get_settings
from app.models import Task, TaskStatus
from app.workers import coding_agent

log = structlog.get_logger()
settings = get_settings()

# Sync engine for Celery workers (aiosqlite is async-only)
_sync_url = settings.database_url.replace("+aiosqlite", "")
_engine = create_engine(_sync_url, connect_args={"check_same_thread": False})
SyncSession = sessionmaker(bind=_engine, expire_on_commit=False)


def _get_task(db: Session, task_id: str) -> Task | None:
    return db.query(Task).filter(Task.id == task_id).first()


# ─── Tasks ────────────────────────────────────────────────────────────────────

@celery_app.task(bind=True, name="run_coding_pipeline", max_retries=1)
def run_coding_pipeline(self, task_id: str) -> dict:
    log.info("celery.run_coding_pipeline.start", task_id=task_id)
    with SyncSession() as db:
        task = _get_task(db, task_id)
        if not task:
            log.error("celery.task_not_found", task_id=task_id)
            return {"status": "not_found"}
        try:
            coding_agent.run_pipeline(task, db)
            return {"status": task.status}
        except Exception as e:
            log.error("celery.pipeline_error", task_id=task_id, exc=str(e))
            task.status = TaskStatus.FAILED
            task.error = str(e)
            db.commit()
            raise self.retry(exc=e, countdown=5)


@celery_app.task(bind=True, name="run_pr_creation", max_retries=2)
def run_pr_creation(self, task_id: str) -> dict:
    log.info("celery.run_pr_creation.start", task_id=task_id)
    with SyncSession() as db:
        task = _get_task(db, task_id)
        if not task:
            log.error("celery.task_not_found", task_id=task_id)
            return {"status": "not_found"}
        try:
            coding_agent.run_pr_creation(task, db)
            return {"status": task.status, "pr_url": task.pr_url}
        except Exception as e:
            log.error("celery.pr_error", task_id=task_id, exc=str(e))
            task.status = TaskStatus.FAILED
            task.error = str(e)
            db.commit()
            raise self.retry(exc=e, countdown=10)
