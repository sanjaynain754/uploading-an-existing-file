"""
Admin API — full control endpoints.
All routes require valid Admin JWT token.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.models import Task, TaskStatus, AdminUser
from app.services.auth_service import (
    authenticate_admin, create_admin, create_token,
    decode_token, get_admin_by_email, hash_password
)

# Sync session for auth (uses same pattern as workers)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import get_settings

settings = get_settings()
_sync_url = settings.database_url.replace("+aiosqlite", "")
_engine   = create_engine(_sync_url, connect_args={"check_same_thread": False})
SyncSession = sessionmaker(bind=_engine, expire_on_commit=False)

router = APIRouter(prefix="/admin", tags=["admin"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email:    str
    password: str

class LoginResponse(BaseModel):
    token:  str
    name:   str
    email:  str
    msg:    str = "Login successful"

class AdminCreate(BaseModel):
    email:    str
    password: str
    name:     str = "Admin"

class SettingsUpdate(BaseModel):
    anthropic_model:  Optional[str] = None
    sandbox_timeout:  Optional[int] = None
    github_repo:      Optional[str] = None

class TaskAction(BaseModel):
    action:  str   # "retry" | "delete" | "cancel"

class ChangePassword(BaseModel):
    old_password: str
    new_password: str


# ─── Auth dependency ──────────────────────────────────────────────────────────

def require_admin(authorization: str = Header(None)) -> dict:
    """Extract and validate JWT from Authorization: Bearer <token>"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header missing")
    token   = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload or payload.get("role") != "admin":
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


# ─── Auth routes ──────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
def admin_login(body: LoginRequest):
    """Admin email + password login → JWT token."""
    with SyncSession() as db:
        admin = authenticate_admin(db, body.email, body.password)
        if not admin:
            raise HTTPException(status_code=401, detail="Email या Password गलत है")
        token = create_token(admin.id, admin.email)
        return LoginResponse(token=token, name=admin.name, email=admin.email)


@router.post("/setup", response_model=LoginResponse)
def admin_setup(body: AdminCreate):
    """First-time admin setup — only works if NO admin exists."""
    with SyncSession() as db:
        count = db.query(func.count(AdminUser.id)).scalar()
        if count > 0:
            raise HTTPException(status_code=403, detail="Admin already exists. Use /admin/login")
        admin = create_admin(db, body.email, body.password, body.name)
        token = create_token(admin.id, admin.email)
        return LoginResponse(token=token, name=admin.name, email=admin.email)


@router.get("/me")
def get_me(admin: dict = Depends(require_admin)):
    """Current admin info."""
    with SyncSession() as db:
        a = db.query(AdminUser).filter(AdminUser.id == admin["sub"]).first()
        if not a:
            raise HTTPException(status_code=404, detail="Admin not found")
        return {
            "id":         a.id,
            "email":      a.email,
            "name":       a.name,
            "last_login": a.last_login,
            "created_at": a.created_at,
        }


@router.post("/change-password")
def change_password(body: ChangePassword, admin: dict = Depends(require_admin)):
    with SyncSession() as db:
        a = db.query(AdminUser).filter(AdminUser.id == admin["sub"]).first()
        from app.services.auth_service import verify_password
        if not verify_password(body.old_password, a.password_hash):
            raise HTTPException(status_code=400, detail="पुराना password गलत है")
        a.password_hash = hash_password(body.new_password)
        db.commit()
        return {"msg": "Password बदल गया ✓"}


# ─── Dashboard stats ──────────────────────────────────────────────────────────

@router.get("/dashboard")
def get_dashboard(admin: dict = Depends(require_admin)):
    """Summary stats for admin dashboard."""
    with SyncSession() as db:
        total     = db.query(func.count(Task.id)).scalar()
        completed = db.query(func.count(Task.id)).filter(Task.status == TaskStatus.COMPLETED).scalar()
        failed    = db.query(func.count(Task.id)).filter(Task.status == TaskStatus.FAILED).scalar()
        pending   = db.query(func.count(Task.id)).filter(
            Task.status.in_([TaskStatus.PENDING, TaskStatus.PLANNING,
                             TaskStatus.CODING, TaskStatus.SCANNING,
                             TaskStatus.TESTING])
        ).scalar()
        awaiting  = db.query(func.count(Task.id)).filter(
            Task.status == TaskStatus.AWAITING_APPROVAL
        ).scalar()
        recent    = db.query(Task).order_by(Task.created_at.desc()).limit(5).all()

        return {
            "stats": {
                "total":     total,
                "completed": completed,
                "failed":    failed,
                "pending":   pending,
                "awaiting_approval": awaiting,
                "success_rate": round(completed / total * 100, 1) if total else 0,
            },
            "recent_tasks": [
                {
                    "id":     t.id,
                    "title":  t.title,
                    "status": t.status,
                    "pr_url": t.pr_url,
                    "created_at": t.created_at,
                }
                for t in recent
            ]
        }


# ─── Task management ──────────────────────────────────────────────────────────

@router.get("/tasks")
def admin_list_tasks(
    skip:   int = 0,
    limit:  int = 50,
    status: Optional[str] = None,
    admin:  dict = Depends(require_admin)
):
    with SyncSession() as db:
        q = db.query(Task)
        if status:
            q = q.filter(Task.status == status)
        tasks = q.order_by(Task.created_at.desc()).offset(skip).limit(limit).all()
        return [
            {
                "id":          t.id,
                "title":       t.title,
                "status":      t.status,
                "test_passed": t.test_passed,
                "pr_url":      t.pr_url,
                "error":       t.error,
                "created_at":  t.created_at,
            }
            for t in tasks
        ]


@router.get("/tasks/{task_id}")
def admin_get_task(task_id: str, admin: dict = Depends(require_admin)):
    with SyncSession() as db:
        t = db.query(Task).filter(Task.id == task_id).first()
        if not t:
            raise HTTPException(status_code=404, detail="Task not found")
        return {
            "id":          t.id,
            "title":       t.title,
            "description": t.description,
            "status":      t.status,
            "plan":        t.plan,
            "code":        t.code,
            "scan_report": t.scan_report,
            "test_output": t.test_output,
            "test_passed": t.test_passed,
            "pr_url":      t.pr_url,
            "error":       t.error,
            "github_repo": t.github_repo,
            "created_at":  t.created_at,
        }


@router.delete("/tasks/{task_id}")
def admin_delete_task(task_id: str, admin: dict = Depends(require_admin)):
    with SyncSession() as db:
        t = db.query(Task).filter(Task.id == task_id).first()
        if not t:
            raise HTTPException(status_code=404, detail="Task not found")
        db.delete(t)
        db.commit()
        return {"msg": f"Task {task_id[:8]} delete हो गई ✓"}


@router.post("/tasks/{task_id}/retry")
def admin_retry_task(task_id: str, admin: dict = Depends(require_admin)):
    """Reset a failed task and re-queue it."""
    with SyncSession() as db:
        t = db.query(Task).filter(Task.id == task_id).first()
        if not t:
            raise HTTPException(status_code=404, detail="Task not found")
        t.status = TaskStatus.PENDING
        t.error  = None
        db.commit()
    from app.workers.tasks import run_coding_pipeline
    run_coding_pipeline.delay(task_id)
    return {"msg": "Task retry हो रही है ✓"}


# ─── Settings ─────────────────────────────────────────────────────────────────

@router.get("/settings")
def get_settings_view(admin: dict = Depends(require_admin)):
    return {
        "anthropic_model":  settings.anthropic_model,
        "sandbox_timeout":  settings.sandbox_timeout,
        "github_repo":      settings.github_repo,
        "sandbox_image":    settings.sandbox_image,
        "app_env":          settings.app_env,
    }


@router.patch("/settings")
def update_settings(body: SettingsUpdate, admin: dict = Depends(require_admin)):
    """
    Runtime settings update (reloads config values in memory).
    For permanent changes, update the .env file and restart.
    """
    changed = {}
    if body.anthropic_model:
        settings.anthropic_model = body.anthropic_model
        changed["anthropic_model"] = body.anthropic_model
    if body.sandbox_timeout:
        settings.sandbox_timeout = body.sandbox_timeout
        changed["sandbox_timeout"] = body.sandbox_timeout
    if body.github_repo:
        settings.github_repo = body.github_repo
        changed["github_repo"] = body.github_repo
    return {"msg": "Settings update हो गईं ✓", "changed": changed}
