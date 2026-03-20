"""Tests for agentutils-install CLI."""

import subprocess


def test_help():
    """CLI runs and shows help."""
    result = subprocess.run(
        ["uv", "run", "agentutils", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "install" in result.stdout.lower()


def test_tool_description():
    result = subprocess.run(
        ["uv", "run", "agentutils", "tool-description"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "agentutils" in result.stdout


def test_tool_description_short():
    result = subprocess.run(
        ["uv", "run", "agentutils", "tool-description-short"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "agentutils" in result.stdout


def test_status():
    """Status command runs without error."""
    result = subprocess.run(
        ["uv", "run", "agentutils", "status"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
