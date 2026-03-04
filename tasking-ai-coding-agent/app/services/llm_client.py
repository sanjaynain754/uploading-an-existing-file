"""
LLM client — wraps Anthropic Claude for the coding agent.
All prompts live here for easy iteration.
"""
from __future__ import annotations
import anthropic
import structlog
from app.config import get_settings

log = structlog.get_logger()
settings = get_settings()

_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


# ─── Prompts ──────────────────────────────────────────────────────────────────

SYSTEM_PLANNER = """You are a senior software architect. Given a task description you will
produce a concise, numbered implementation plan (max 10 steps). Be specific about file names,
function signatures, and edge cases. Output ONLY the plan, no preamble."""

SYSTEM_CODER = """You are an expert Python developer. Given an implementation plan you will
produce clean, well-commented, production-ready Python code. 
Output ONLY a single fenced code block with the complete implementation.
Do not include any explanation outside the code block."""

SYSTEM_REVIEWER = """You are a code reviewer. Given code and its SAST scan report, write a
brief human-readable summary of any security or quality issues found. Be concise."""


# ─── Public helpers ───────────────────────────────────────────────────────────

def generate_plan(task_title: str, task_description: str) -> str:
    log.info("llm.generate_plan", title=task_title)
    msg = get_client().messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=SYSTEM_PLANNER,
        messages=[
            {
                "role": "user",
                "content": f"Task: {task_title}\n\nDescription:\n{task_description}",
            }
        ],
    )
    return msg.content[0].text


def generate_code(task_title: str, plan: str) -> str:
    log.info("llm.generate_code", title=task_title)
    msg = get_client().messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        system=SYSTEM_CODER,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Task: {task_title}\n\n"
                    f"Implementation Plan:\n{plan}\n\n"
                    "Write the complete Python implementation."
                ),
            }
        ],
    )
    raw = msg.content[0].text
    # strip fences if present
    return _strip_fences(raw)


def summarise_scan(code: str, scan_report: dict) -> str:
    log.info("llm.summarise_scan")
    msg = get_client().messages.create(
        model=settings.anthropic_model,
        max_tokens=512,
        system=SYSTEM_REVIEWER,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Code:\n```python\n{code[:3000]}\n```\n\n"
                    f"SAST Report:\n{scan_report}"
                ),
            }
        ],
    )
    return msg.content[0].text


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    """Remove leading/trailing ```python ... ``` fences."""
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)
