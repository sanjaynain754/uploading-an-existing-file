"""
GitHub integration: creates a branch, commits generated code, and opens a PR.
"""
from __future__ import annotations
import re
import uuid
import structlog
from github import Github, GithubException
from app.config import get_settings

log = structlog.get_logger()
settings = get_settings()


def create_pr(
    task_id: str,
    task_title: str,
    task_description: str,
    code: str,
    plan: str,
    repo_name: str | None = None,
) -> str:
    """
    Creates a GitHub PR with the generated code.
    Returns the PR URL.
    """
    repo_name = repo_name or settings.github_repo
    if not repo_name:
        raise ValueError("No GitHub repo configured (GITHUB_REPO env var or task.github_repo)")

    g = Github(settings.github_token)
    repo = g.get_repo(repo_name)

    branch_name = _branch_name(task_title, task_id)
    base_sha = repo.get_branch(repo.default_branch).commit.sha

    # Create branch
    try:
        repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_sha)
        log.info("git.branch_created", branch=branch_name)
    except GithubException as e:
        log.error("git.branch_error", error=str(e))
        raise

    # Determine file path from task title
    file_path = _file_path(task_title)

    # Commit code
    try:
        repo.create_file(
            path=file_path,
            message=f"feat: {task_title} (task {task_id[:8]})",
            content=code,
            branch=branch_name,
        )
        log.info("git.file_committed", path=file_path)
    except GithubException as e:
        log.error("git.commit_error", error=str(e))
        raise

    # Open PR
    pr_body = _pr_body(task_description, plan)
    pr = repo.create_pull(
        title=f"[AI] {task_title}",
        body=pr_body,
        head=branch_name,
        base=repo.default_branch,
    )
    log.info("git.pr_created", url=pr.html_url)
    return pr.html_url


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _branch_name(title: str, task_id: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40]
    return f"ai/{slug}-{task_id[:8]}"


def _file_path(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:30]
    return f"generated/{slug}.py"


def _pr_body(description: str, plan: str) -> str:
    return f"""## 🤖 AI-Generated Code

### Task Description
{description}

### Implementation Plan
{plan}

---
*This PR was created automatically by the AI Coding Agent.*
*Please review the code carefully before merging.*
"""
