"""Tests for gitro CLI entry point."""

import subprocess
from unittest.mock import patch

import pytest

from gitro.cli import main


class TestMetaCommands:
    """Meta-commands should print help text and not invoke git."""

    def test_tool_description(self, capsys):
        with patch("sys.argv", ["gitro", "tool-description"]):
            main()
        out = capsys.readouterr().out
        assert "gitro" in out
        assert "Read-only" in out or "read-only" in out

    def test_tool_description_short(self, capsys):
        with patch("sys.argv", ["gitro", "tool-description-short"]):
            main()
        out = capsys.readouterr().out
        assert "gitro" in out
        assert len(out) < 1000  # should be concise

    def test_allowed(self, capsys):
        with patch("sys.argv", ["gitro", "allowed"]):
            main()
        out = capsys.readouterr().out
        assert "log" in out
        assert "branch" in out
        assert "Unconditionally" in out or "unconditionally" in out.lower()

    def test_help(self, capsys):
        with patch("sys.argv", ["gitro", "help"]):
            main()
        out = capsys.readouterr().out
        assert "gitro" in out

    def test_help_subcommand(self, capsys):
        with patch("sys.argv", ["gitro", "help", "allowed"]):
            main()
        out = capsys.readouterr().out
        assert "allowed" in out.lower()

    def test_no_args(self, capsys):
        with patch("sys.argv", ["gitro"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        out = capsys.readouterr().out
        assert "gitro" in out


class TestGitPassthrough:
    """Allowed commands should be passed through to git."""

    def test_allowed_command_calls_git(self):
        mock_result = subprocess.CompletedProcess(args=["git", "log"], returncode=0)
        with patch("sys.argv", ["gitro", "log", "--oneline"]), \
             patch("subprocess.run", return_value=mock_result) as mock_run:
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
            mock_run.assert_called_once_with(["git", "log", "--oneline"])

    def test_allowed_command_preserves_exit_code(self):
        mock_result = subprocess.CompletedProcess(args=["git", "log"], returncode=128)
        with patch("sys.argv", ["gitro", "log"]), \
             patch("subprocess.run", return_value=mock_result) as mock_run:
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 128
            mock_run.assert_called_once()

    def test_global_flags_passed_through(self):
        mock_result = subprocess.CompletedProcess(args=[], returncode=0)
        with patch("sys.argv", ["gitro", "--no-pager", "log"]), \
             patch("subprocess.run", return_value=mock_result) as mock_run:
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
            mock_run.assert_called_once_with(["git", "--no-pager", "log"])


class TestBlockedCommands:
    """Blocked commands should print error and exit 1."""

    def test_commit_blocked(self, capsys):
        with patch("sys.argv", ["gitro", "commit", "-m", "test"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "blocked" in err

    def test_push_blocked(self, capsys):
        with patch("sys.argv", ["gitro", "push"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "blocked" in err

    def test_blocked_does_not_call_git(self):
        with patch("sys.argv", ["gitro", "commit", "-m", "test"]), \
             patch("subprocess.run") as mock_run:
            with pytest.raises(SystemExit):
                main()
            mock_run.assert_not_called()
