from datetime import datetime
from sqlalchemy import (
    Column, String, Text, DateTime, Enum, ForeignKey, JSON, Integer
)
from sqlalchemy.orm import DeclarativeBase, relationship
import enum
import uuid


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


# ─── Enums ────────────────────────────────────────────────────────────────────

class TaskStatus(str, enum.Enum):
    PENDING        = "pending"
    PLANNING       = "planning"
    CODING         = "coding"
    SCANNING       = "scanning"
    TESTING        = "testing"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED       = "approved"
    REJECTED       = "rejected"
    CREATING_PR    = "creating_pr"
    COMPLETED      = "completed"
    FAILED         = "failed"


class ApprovalAction(str, enum.Enum):
    APPROVE = "approve"
    REJECT  = "reject"


# ─── Models ───────────────────────────────────────────────────────────────────

class Task(Base):
    __tablename__ = "tasks"

    id          = Column(String, primary_key=True, default=_uuid)
    title       = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    status      = Column(Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)

    # optional target repo override per-task
    github_repo = Column(String(255), nullable=True)

    # outputs
    plan        = Column(Text,   nullable=True)   # LLM-generated plan
    code        = Column(Text,   nullable=True)   # generated code
    scan_report = Column(JSON,   nullable=True)   # SAST results
    test_output = Column(Text,   nullable=True)   # sandbox stdout/stderr
    test_passed = Column(Integer, default=None)   # 1 / 0 / None
    pr_url      = Column(String(512), nullable=True)
    error       = Column(Text,   nullable=True)

    # celery task IDs for tracking
    celery_task_id = Column(String(255), nullable=True)

    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    approvals   = relationship("Approval", back_populates="task", cascade="all, delete-orphan")
    logs        = relationship("TaskLog",  back_populates="task", cascade="all, delete-orphan")


class Approval(Base):
    __tablename__ = "approvals"

    id         = Column(String, primary_key=True, default=_uuid)
    task_id    = Column(String, ForeignKey("tasks.id"), nullable=False)
    action     = Column(Enum(ApprovalAction), nullable=False)
    reviewer   = Column(String(255), default="human")
    comment    = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="approvals")


class TaskLog(Base):
    __tablename__ = "task_logs"

    id         = Column(String, primary_key=True, default=_uuid)
    task_id    = Column(String, ForeignKey("tasks.id"), nullable=False)
    level      = Column(String(20), default="info")
    message    = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("Task", back_populates="logs")
