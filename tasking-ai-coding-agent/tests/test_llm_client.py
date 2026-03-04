"""Unit tests for LLM client helpers."""
import pytest
from unittest.mock import patch, MagicMock
from app.services import llm_client


def _mock_message(text: str):
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


@patch("app.services.llm_client.get_client")
def test_generate_plan(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.messages.create.return_value = _mock_message("1. Step one\n2. Step two")

    plan = llm_client.generate_plan("Build calculator", "A simple calculator")
    assert "Step" in plan
    mock_client.messages.create.assert_called_once()


@patch("app.services.llm_client.get_client")
def test_generate_code_strips_fences(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.messages.create.return_value = _mock_message(
        "```python\ndef add(a, b): return a + b\n```"
    )
    code = llm_client.generate_code("Calculator", "1. Add function")
    assert "```" not in code
    assert "def add" in code


def test_strip_fences_no_fences():
    raw = "def hello(): pass"
    assert llm_client._strip_fences(raw) == raw


def test_strip_fences_with_fences():
    raw = "```python\ndef hello(): pass\n```"
    assert llm_client._strip_fences(raw) == "def hello(): pass"
