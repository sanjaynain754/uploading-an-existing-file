from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Task, TaskStatus, Approval, ApprovalAction
from app.schemas.task_schemas import ApprovalCreate, ApprovalResponse, MessageResponse
from app.workers.tasks import run_pr_creation

router = APIRouter(prefix="/api/tasks", tags=["approvals"])


@router.post("/{task_id}/approve", response_model=ApprovalResponse)
async def approve_or_reject_task(
    task_id: str,
    payload: ApprovalCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f"Task is not awaiting approval (current status: {task.status})",
        )

    # Persist approval record
    approval = Approval(
        task_id=task.id,
        action=payload.action,
        reviewer=payload.reviewer,
        comment=payload.comment,
    )
    db.add(approval)

    if payload.action == ApprovalAction.APPROVE:
        task.status = TaskStatus.APPROVED
        await db.commit()
        # Kick off PR creation
        job = run_pr_creation.delay(task.id)
        task.celery_task_id = job.id
        await db.commit()
    else:
        task.status = TaskStatus.REJECTED
        await db.commit()

    await db.refresh(approval)
    return approval
