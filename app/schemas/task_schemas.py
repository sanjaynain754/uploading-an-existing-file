from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field
from app.models import TaskStatus, ApprovalAction


# ─── Task ─────────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title:       str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=10)
    github_repo: Optional[str] = None   # override default repo


class TaskSummary(BaseModel):
    id:          str
    title:       str
    status:      TaskStatus
    pr_url:      Optional[str]
    created_at:  datetime
    updated_at:  datetime

    model_config = {"from_attributes": True}


class TaskDetail(TaskSummary):
    description: str
    plan:        Optional[str]
    code:        Optional[str]
    scan_report: Optional[Any]
    test_output: Optional[str]
    test_passed: Optional[int]
    error:       Optional[str]
    github_repo: Optional[str]
    logs:        List[LogEntry] = []

    model_config = {"from_attributes": True}


class LogEntry(BaseModel):
    level:      str
    message:    str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Approval ─────────────────────────────────────────────────────────────────

class ApprovalCreate(BaseModel):
    action:   ApprovalAction
    reviewer: str = "human"
    comment:  Optional[str] = None


class ApprovalResponse(BaseModel):
    id:         str
    task_id:    str
    action:     ApprovalAction
    reviewer:   str
    comment:    Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Generic ──────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str


# Fix forward reference
TaskDetail.model_rebuild()
