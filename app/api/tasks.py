from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Task, TaskStatus
from app.schemas.task_schemas import TaskCreate, TaskDetail, TaskSummary
from app.workers.tasks import run_coding_pipeline

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ── POST /api/tasks ────────────────────────────────────────────────────────────

@router.post("/", response_model=TaskSummary, status_code=status.HTTP_201_CREATED)
async def create_task(payload: TaskCreate, db: AsyncSession = Depends(get_db)):
    task = Task(
        title=payload.title,
        description=payload.description,
        github_repo=payload.github_repo,
    )
    db.add(task)
    await db.flush()   # get task.id before commit

    # Kick off background pipeline
    job = run_coding_pipeline.delay(task.id)
    task.celery_task_id = job.id

    await db.commit()
    await db.refresh(task)
    return task


# ── GET /api/tasks ─────────────────────────────────────────────────────────────

@router.get("/", response_model=List[TaskSummary])
async def list_tasks(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Task).order_by(Task.created_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()


# ── GET /api/tasks/{id} ────────────────────────────────────────────────────────

@router.get("/{task_id}", response_model=TaskDetail)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.logs))
        .where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# ── DELETE /api/tasks/{id} ─────────────────────────────────────────────────────

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    await db.commit()
