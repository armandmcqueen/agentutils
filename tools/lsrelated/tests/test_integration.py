"""Integration tests for lsrelated CLI — runs the real command as a subprocess."""

import subprocess
import sys

import pytest

from ccdata.testing import SessionBuilder, ClaudeDirBuilder


def run_lsrelated(*args: str) -> subprocess.CompletedProcess:
    """Run lsrelated as a subprocess, the way a user would."""
    return subprocess.run(
        [sys.executable, "-m", "lsrelated", *args],
        capture_output=True,
        text=True,
    )


class TestRelated:
    def test_related_finds_coaccessed_files(self, tmp_path):
        """Files read together more often rank higher."""
        builder = SessionBuilder()
        for _ in range(3):
            builder.add_turn("work", file_reads=["/a.py", "/b.py"])
        builder.add_turn("more work", file_reads=["/a.py", "/c.py"])

        claude_dir = ClaudeDirBuilder(tmp_path).add_session(builder).build()
        result = run_lsrelated("related", "/a.py", "--claude-dir", str(claude_dir))

        assert result.returncode == 0
        # /b.py should appear before /c.py (weight 3 vs 1)
        output = result.stdout
        b_pos = output.index("/b.py")
        c_pos = output.index("/c.py")
        assert b_pos < c_pos, f"/b.py should rank higher than /c.py:\n{output}"
        assert "3" in output  # weight 3 for /b.py

    def test_top_ranks_by_total_weight(self, tmp_path):
        """top command ranks files by total edge weight."""
        builder = SessionBuilder()
        for _ in range(3):
            builder.add_turn("work", file_reads=["/a.py", "/b.py"])
        builder.add_turn("other", file_reads=["/c.py", "/d.py"])

        claude_dir = ClaudeDirBuilder(tmp_path).add_session(builder).build()
        result = run_lsrelated("top", "--claude-dir", str(claude_dir))

        assert result.returncode == 0
        output = result.stdout
        a_pos = output.index("/a.py")
        c_pos = output.index("/c.py")
        assert a_pos < c_pos

    def test_no_subagents_excludes_subagent_edges(self, tmp_path):
        """--no-subagents excludes subagent file reads from the graph."""
        builder = (
            SessionBuilder()
            .add_subagent_turn(
                "Research",
                agent_description="find files",
                subagent_file_reads=["/sub.py"],
                parent_file_reads=["/main.py"],
            )
        )
        claude_dir = ClaudeDirBuilder(tmp_path).add_session(builder).build()

        # With subagents: /sub.py should appear as related to /main.py
        result = run_lsrelated("related", "/main.py", "--claude-dir", str(claude_dir))
        assert result.returncode == 0
        assert "/sub.py" in result.stdout

        # Without subagents: /sub.py should NOT appear
        result = run_lsrelated("related", "/main.py", "--no-subagents", "--claude-dir", str(claude_dir))
        assert "/sub.py" not in result.stdout

    def test_related_partial_match(self, tmp_path):
        """Partial file name resolves correctly through the full pipeline."""
        builder = (
            SessionBuilder()
            .add_turn("work", file_reads=["/src/lib/types.ts", "/src/lib/utils.ts"])
        )
        claude_dir = ClaudeDirBuilder(tmp_path).add_session(builder).build()

        result = run_lsrelated("related", "types.ts", "--claude-dir", str(claude_dir))
        assert result.returncode == 0
        assert "utils.ts" in result.stdout

    def test_related_no_match_shows_error(self, tmp_path):
        """Non-existent file shows error message."""
        builder = SessionBuilder().add_turn("work", file_reads=["/a.py"])
        claude_dir = ClaudeDirBuilder(tmp_path).add_session(builder).build()

        result = run_lsrelated("related", "nonexistent.xyz", "--claude-dir", str(claude_dir))
        assert result.returncode == 1
        assert "No file matching" in result.stderr or "No file matching" in result.stdout
