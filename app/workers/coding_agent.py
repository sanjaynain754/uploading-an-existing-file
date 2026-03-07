"""
The core coding agent pipeline.
Runs synchronously inside a Celery task.
Persists state to SQLite after each step.
"""
from __future__ import annotations
import structlog
from sqlalchemy.orm import Session

from app.models import Task, TaskLog, TaskStatus
from app.services import llm_client, code_scanner, sandbox, git_service

log = structlog.get_logger()


def run_pipeline(task: Task, db: Session) -> None:
    """
    Full pipeline:
      1. Plan  →  2. Code  →  3. Scan  →  4. Test  →  5. Await Approval  →  6. PR
    Raises on unrecoverable errors; caller marks task FAILED.
    """
    _log(db, task, "info", "Pipeline started")

    # ── 1. Planning ──────────────────────────────────────────────────────────
    _set_status(db, task, TaskStatus.PLANNING)
    _log(db, task, "info", "Generating implementation plan…")
    plan = llm_client.generate_plan(task.title, task.description)
    task.plan = plan
    db.commit()
    _log(db, task, "info", f"Plan generated ({len(plan)} chars)")

    # ── 2. Code generation ───────────────────────────────────────────────────
    _set_status(db, task, TaskStatus.CODING)
    _log(db, task, "info", "Generating code…")
    code = llm_client.generate_code(task.title, plan)
    task.code = code
    db.commit()
    _log(db, task, "info", f"Code generated ({len(code)} chars)")

    # ── 3. SAST scan ─────────────────────────────────────────────────────────
    _set_status(db, task, TaskStatus.SCANNING)
    _log(db, task, "info", "Running static analysis…")
    scan_report = code_scanner.scan_code(code)
    task.scan_report = scan_report
    db.commit()

    if not scan_report["passed"]:
        summary = llm_client.summarise_scan(code, scan_report)
        _log(db, task, "warning", f"Scan issues found: {summary}")
    else:
        _log(db, task, "info", "Scan passed ✓")

    # ── 4. Sandbox execution ──────────────────────────────────────────────────
    _set_status(db, task, TaskStatus.TESTING)
    _log(db, task, "info", "Executing code in sandbox…")
    result = sandbox.run_in_sandbox(code)
    task.test_output = f"STDOUT:\n{result['stdout']}\nSTDERR:\n{result['stderr']}"
    task.test_passed = 1 if result["passed"] else 0
    db.commit()

    if result["error"]:
        _log(db, task, "warning", f"Sandbox error: {result['error']}")
    elif result["passed"]:
        _log(db, task, "info", "Sandbox execution passed ✓")
    else:
        _log(db, task, "warning", f"Sandbox exit code {result['exit_code']}")

    # ── 5. Await human approval ───────────────────────────────────────────────
    _set_status(db, task, TaskStatus.AWAITING_APPROVAL)
    _log(db, task, "info", "Waiting for human approval…")
    # The pipeline pauses here. The approval endpoint will re-trigger PR creation.


def run_pr_creation(task: Task, db: Session) -> None:
    """Called after approval is granted."""
    _set_status(db, task, TaskStatus.CREATING_PR)
    _log(db, task, "info", "Creating GitHub PR…")
    try:
        pr_url = git_service.create_pr(
            task_id=task.id,
            task_title=task.title,
            task_description=task.description,
            code=task.code,
            plan=task.plan,
            repo_name=task.github_repo,
        )
        task.pr_url = pr_url
        _set_status(db, task, TaskStatus.COMPLETED)
        _log(db, task, "info", f"PR created: {pr_url}")
    except Exception as e:
        _log(db, task, "error", f"PR creation failed: {e}")
        raise


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _set_status(db: Session, task: Task, status: TaskStatus) -> None:
    task.status = status
    db.commit()
    log.info("task.status", task_id=task.id, status=status)


def _log(db: Session, task: Task, level: str, message: str) -> None:
    entry = TaskLog(task_id=task.id, level=level, message=message)
    db.add(entry)
    db.commit()
    getattr(log, level, log.info)(message, task_id=task.id)
