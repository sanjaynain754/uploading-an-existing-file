# 🤖 AI Coding Agent

A production-ready task queue system that accepts coding tasks, uses **Claude** to plan and write code, scans it for security issues, runs it in an isolated Docker sandbox, waits for human approval, then raises a GitHub PR — automatically.

---

## Architecture

```
POST /api/tasks
      │
      ▼
 FastAPI API  ──► Celery Task ──► Coding Agent Pipeline
                                       │
                    ┌──────────────────┼──────────────────────┐
                    ▼                  ▼                       ▼
              LLM Planner       Code Generator          SAST Scanner
              (Claude)          (Claude)                (bandit + pylint)
                                       │
                                       ▼
                                Docker Sandbox
                                (execute & test)
                                       │
                                       ▼
                              AWAITING_APPROVAL
                                       │
                          POST /api/tasks/{id}/approve
                                       │
                                       ▼
                              GitHub PR Created ✓
```

## Stack

| Layer | Tech |
|-------|------|
| API | FastAPI + uvicorn |
| Queue | Celery + Redis |
| DB | SQLite (async via aiosqlite) |
| LLM | Anthropic Claude |
| Sandbox | Docker (isolated, no network, 256 MB RAM) |
| Scanning | bandit (security) + pylint (quality) |
| VCS | GitHub API (PyGithub) |
| Monitoring | Flower (Celery UI) |

---

## Quick Start

### 1. Clone & configure

```bash
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY, GITHUB_TOKEN, GITHUB_REPO
```

### 2. Run with Docker Compose

```bash
docker compose up --build
```

Services:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **Flower**: http://localhost:5555

### 3. Run locally (no Docker Compose)

```bash
# Prerequisites: Redis running on localhost:6379
pip install -r requirements.txt

# Start API
uvicorn app.main:app --reload

# Start worker (separate terminal)
celery -A app.workers.celery_app:celery_app worker --loglevel=info
```

---

## API Reference

### Submit a task

```bash
curl -X POST http://localhost:8000/api/tasks/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Binary search implementation",
    "description": "Write a Python binary search function with edge case handling and tests.",
    "github_repo": "owner/my-repo"
  }'
```

### Poll task status

```bash
curl http://localhost:8000/api/tasks/{task_id}
```

### Approve (or reject)

```bash
# Approve → triggers PR creation
curl -X POST http://localhost:8000/api/tasks/{task_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"action": "approve", "reviewer": "alice", "comment": "LGTM"}'

# Reject
curl -X POST http://localhost:8000/api/tasks/{task_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"action": "reject", "reviewer": "alice", "comment": "Needs more error handling"}'
```

### Task status lifecycle

```
pending → planning → coding → scanning → testing → awaiting_approval
                                                          │
                                              approve ────┤
                                                          ▼
                                                    creating_pr → completed
                                              reject ────► rejected
                                              (any step) ► failed
```

---

## Demo Script

```bash
python scripts/demo_submit_task.py
```

Submits a task, polls until approval is needed, auto-approves, and prints the PR URL.

---

## Tests

```bash
pytest tests/ -v
```

---

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | — |
| `ANTHROPIC_MODEL` | Model to use | `claude-opus-4-5` |
| `GITHUB_TOKEN` | GitHub PAT with `repo` scope | — |
| `GITHUB_REPO` | Default `owner/repo` for PRs | — |
| `SANDBOX_IMAGE` | Docker image for code execution | `python:3.12-slim` |
| `SANDBOX_TIMEOUT` | Max execution time (seconds) | `30` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |

---

## Security notes

- Sandbox containers run with `--network=none`, `--read-only`, `--memory=256m`
- Generated code is scanned by bandit before execution
- Human approval is required before any PR is created
- No secrets are committed to generated branches
