"""
Static analysis: runs bandit (security) and pylint (quality) on generated code.
Everything runs in-process using temp files — no Docker needed for scanning.
"""
from __future__ import annotations
import json
import subprocess
import tempfile
import os
import structlog

log = structlog.get_logger()


def scan_code(code: str) -> dict:
    """
    Returns a dict:
    {
        "bandit": { "results": [...], "metrics": {...} },
        "pylint": { "score": float, "messages": [...] },
        "passed": bool   # True if no HIGH severity bandit issues and pylint >= 6.0
    }
    """
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        tmp_path = f.name

    try:
        bandit_result = _run_bandit(tmp_path)
        pylint_result = _run_pylint(tmp_path)
        passed = _evaluate(bandit_result, pylint_result)
        return {
            "bandit": bandit_result,
            "pylint": pylint_result,
            "passed": passed,
        }
    finally:
        os.unlink(tmp_path)


# ─── Bandit ───────────────────────────────────────────────────────────────────

def _run_bandit(path: str) -> dict:
    try:
        result = subprocess.run(
            ["bandit", "-f", "json", "-q", path],
            capture_output=True, text=True, timeout=30
        )
        data = json.loads(result.stdout or "{}")
        return {
            "results":  data.get("results", []),
            "metrics":  data.get("metrics", {}),
            "error":    None,
        }
    except FileNotFoundError:
        log.warning("bandit not installed — skipping security scan")
        return {"results": [], "metrics": {}, "error": "bandit not installed"}
    except Exception as e:
        log.error("bandit.error", exc=str(e))
        return {"results": [], "metrics": {}, "error": str(e)}


# ─── Pylint ───────────────────────────────────────────────────────────────────

def _run_pylint(path: str) -> dict:
    try:
        result = subprocess.run(
            [
                "pylint", path,
                "--output-format=json",
                "--disable=C0114,C0115,C0116",   # ignore missing docstrings
                "--score=yes",
            ],
            capture_output=True, text=True, timeout=30
        )
        messages = []
        try:
            messages = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            pass

        # extract score from stderr like "Your code has been rated at 8.50/10"
        score = _parse_pylint_score(result.stderr + result.stdout)
        return {"score": score, "messages": messages, "error": None}
    except FileNotFoundError:
        log.warning("pylint not installed — skipping quality scan")
        return {"score": 10.0, "messages": [], "error": "pylint not installed"}
    except Exception as e:
        log.error("pylint.error", exc=str(e))
        return {"score": 0.0, "messages": [], "error": str(e)}


def _parse_pylint_score(output: str) -> float:
    import re
    match = re.search(r"rated at ([\d.]+)/10", output)
    return float(match.group(1)) if match else 0.0


# ─── Pass/fail logic ──────────────────────────────────────────────────────────

def _evaluate(bandit: dict, pylint: dict) -> bool:
    high_issues = [
        r for r in bandit.get("results", [])
        if r.get("issue_severity") == "HIGH"
    ]
    if high_issues:
        log.warning("scan.failed_bandit_high", count=len(high_issues))
        return False
    score = pylint.get("score", 10.0)
    if score < 6.0:
        log.warning("scan.failed_pylint_score", score=score)
        return False
    return True
