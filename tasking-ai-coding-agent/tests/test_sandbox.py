"""Unit tests for the Docker sandbox runner."""
import pytest
from unittest.mock import patch, MagicMock
from app.services import sandbox


@patch("app.services.sandbox.subprocess.run")
def test_sandbox_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="Hello\n", stderr="")
    result = sandbox.run_in_sandbox("print('Hello')")
    assert result["passed"] is True
    assert result["exit_code"] == 0
    assert "Hello" in result["stdout"]


@patch("app.services.sandbox.subprocess.run")
def test_sandbox_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="SyntaxError")
    result = sandbox.run_in_sandbox("def broken(")
    assert result["passed"] is False
    assert result["exit_code"] == 1


@patch("app.services.sandbox.subprocess.run")
def test_sandbox_timeout(mock_run):
    import subprocess
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker", timeout=30)
    result = sandbox.run_in_sandbox("while True: pass")
    assert result["passed"] is False
    assert "timed out" in result["error"]


@patch("app.services.sandbox.subprocess.run")
def test_sandbox_docker_not_found(mock_run):
    mock_run.side_effect = FileNotFoundError()
    result = sandbox.run_in_sandbox("print('x')")
    assert result["passed"] is False
    assert "Docker not found" in result["error"]
