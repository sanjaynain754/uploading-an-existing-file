"""
Sandbox: runs generated Python code inside a throwaway Docker container.
Requires Docker daemon to be accessible from the host running the worker.
"""
from __future__ import annotations
import subprocess
import tempfile
import os
import structlog
from app.config import get_settings

log = structlog.get_logger()
settings = get_settings()


def run_in_sandbox(code: str) -> dict:
    """
    Executes `code` inside a Docker container.

    Returns:
    {
        "stdout": str,
        "stderr": str,
        "exit_code": int,
        "passed": bool,
        "error": str | None,
    }
    """
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        host_path = f.name

    container_path = "/tmp/solution.py"

    cmd = [
        "docker", "run",
        "--rm",
        "--network=none",          # no outbound network
        "--memory=256m",
        "--cpus=0.5",
        "--read-only",
        "--tmpfs", "/tmp:size=64m",
        "-v", f"{host_path}:{container_path}:ro",
        settings.sandbox_image,
        "python", container_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=settings.sandbox_timeout,
        )
        passed = result.returncode == 0
        return {
            "stdout":    result.stdout,
            "stderr":    result.stderr,
            "exit_code": result.returncode,
            "passed":    passed,
            "error":     None,
        }
    except subprocess.TimeoutExpired:
        log.error("sandbox.timeout", timeout=settings.sandbox_timeout)
        return {
            "stdout": "", "stderr": "",
            "exit_code": -1, "passed": False,
            "error": f"Execution timed out after {settings.sandbox_timeout}s",
        }
    except FileNotFoundError:
        log.error("sandbox.docker_not_found")
        return {
            "stdout": "", "stderr": "",
            "exit_code": -1, "passed": False,
            "error": "Docker not found — is the Docker daemon running?",
        }
    except Exception as e:
        log.error("sandbox.error", exc=str(e))
        return {
            "stdout": "", "stderr": "",
            "exit_code": -1, "passed": False,
            "error": str(e),
        }
    finally:
        os.unlink(host_path)
