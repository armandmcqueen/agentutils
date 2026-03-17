"""Tests for lsrelated CLI meta-commands."""

import subprocess
import sys


def test_tool_description():
    result = subprocess.run(
        [sys.executable, "-m", "lsrelated.cli"],
        capture_output=True, text=True,
        env={"PATH": ""},
    )
    # No args should show help (typer no_args_is_help)
    # Just verify it doesn't crash
    assert result.returncode == 0 or "Usage" in result.stdout or "Usage" in result.stderr


def test_tool_description_command():
    from typer.testing import CliRunner
    from lsrelated.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["tool-description"])
    assert result.exit_code == 0
    assert "lsrelated" in result.output
    assert "related" in result.output


def test_tool_description_short_command():
    from typer.testing import CliRunner
    from lsrelated.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["tool-description-short"])
    assert result.exit_code == 0
    assert "lsrelated" in result.output


def test_related_help():
    from typer.testing import CliRunner
    from lsrelated.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["related", "--help"])
    assert result.exit_code == 0
    assert "file" in result.output.lower()


def test_top_help():
    from typer.testing import CliRunner
    from lsrelated.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["top", "--help"])
    assert result.exit_code == 0
    assert "top" in result.output.lower() or "files" in result.output.lower()
