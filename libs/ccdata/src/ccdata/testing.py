"""Shared test fixture builders for ccdata.

Provides entry builders and high-level session/directory builders for
constructing realistic Claude Code session data on disk. Used by ccdata's
own tests and by downstream tools (e.g. lsrelated) for integration testing.

Usage:
    from ccdata.testing import SessionBuilder, ClaudeDirBuilder

    builder = (
        SessionBuilder(project_key="-test-project", session_id="sess-001")
        .add_turn("Read a file", file_reads=["/src/main.py"])
        .add_turn("Edit it", file_edits=["/src/main.py"], file_writes=["/src/util.py"])
    )

    claude_dir = ClaudeDirBuilder(tmp_path).add_session(builder).build()
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Self


# -- Entry builders --


def user_text_entry(text: str, timestamp: str = "2026-03-01T00:00:00Z", **extra) -> dict:
    """A user entry with a text content block."""
    return {
        "type": "user",
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
        "timestamp": timestamp,
        "sessionId": "test-session",
        "version": "2.1.71",
        "gitBranch": "main",
        "slug": "test-slug",
        **extra,
    }


def user_string_entry(text: str, timestamp: str = "2026-03-01T00:00:00Z") -> dict:
    """A user entry with string content (older format)."""
    return {
        "type": "user",
        "message": {"role": "user", "content": text},
        "timestamp": timestamp,
        "sessionId": "test-session",
    }


def user_tool_result_entry(tool_use_id: str, result: str, is_error: bool = False) -> dict:
    """A user entry carrying a tool_result block."""
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": result,
                    "is_error": is_error,
                }
            ],
        },
        "timestamp": "2026-03-01T00:01:00Z",
        "sessionId": "test-session",
    }


def assistant_entry(
    content_blocks: list[dict],
    usage: dict | None = None,
    request_id: str = "req-1",
    model: str = "claude-opus-4-6",
    stop_reason: str = "end_turn",
    timestamp: str = "2026-03-01T00:00:30Z",
) -> dict:
    """An assistant entry with given content blocks and usage."""
    return {
        "type": "assistant",
        "requestId": request_id,
        "message": {
            "model": model,
            "role": "assistant",
            "type": "message",
            "stop_reason": stop_reason,
            "content": content_blocks,
            "usage": usage or {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_input_tokens": 200,
                "cache_creation_input_tokens": 300,
            },
        },
        "timestamp": timestamp,
        "sessionId": "test-session",
        "version": "2.1.71",
        "gitBranch": "main",
        "slug": "test-slug",
    }


def system_turn_duration(duration_ms: int = 5000) -> dict:
    return {
        "type": "system",
        "subtype": "turn_duration",
        "durationMs": duration_ms,
        "timestamp": "2026-03-01T00:01:00Z",
        "sessionId": "test-session",
    }


def progress_entry() -> dict:
    return {
        "type": "progress",
        "data": {"type": "hook_progress", "hookEvent": "PostToolUse"},
        "sessionId": "test-session",
    }


def progress_agent_entry(parent_tool_use_id: str, agent_id: str) -> dict:
    """A progress entry linking an Agent tool_use to a subagent file."""
    return {
        "type": "progress",
        "parentToolUseID": parent_tool_use_id,
        "data": {"type": "agent_progress", "agentId": agent_id},
        "sessionId": "test-session",
    }


def file_history_entry() -> dict:
    return {
        "type": "file-history-snapshot",
        "messageId": "msg-1",
        "snapshot": {"messageId": "msg-1", "trackedFileBackups": {}},
    }


# -- High-level builders --


class SessionBuilder:
    """Declaratively build a Claude Code session with turns, tool calls, and subagents.

    Example:
        builder = (
            SessionBuilder()
            .add_turn("Read files", file_reads=["/a.py", "/b.py"])
            .add_subagent_turn("Research", "find files",
                               subagent_file_reads=["/sub/x.py"])
        )
        entries = builder.build_entries()
        path = builder.write(tmp_path)  # writes JSONL + subagent files
    """

    def __init__(
        self,
        project_key: str = "-test-project",
        session_id: str = "sess-001",
        git_branch: str = "main",
    ):
        self.project_key = project_key
        self.session_id = session_id
        self.git_branch = git_branch
        self._turns: list[dict[str, Any]] = []
        self._subagents: list[dict[str, Any]] = []  # [{agent_id, entries}]
        self._next_ts = 1709251200  # 2024-03-01T00:00:00Z base
        self._next_tool_id = 1
        self._next_req_id = 1
        self._next_agent_id = 1

    def _ts(self) -> str:
        from datetime import datetime, timezone
        ts = datetime.fromtimestamp(self._next_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._next_ts += 10
        return ts

    def _tool_id(self) -> str:
        tid = f"tool-{self._next_tool_id:04d}"
        self._next_tool_id += 1
        return tid

    def _req_id(self) -> str:
        rid = f"req-{self._next_req_id:04d}"
        self._next_req_id += 1
        return rid

    def _agent_id(self) -> str:
        aid = f"agent-{self._next_agent_id:04d}"
        self._next_agent_id += 1
        return aid

    def add_turn(
        self,
        user_text: str,
        file_reads: list[str] | None = None,
        file_writes: list[str] | None = None,
        file_edits: list[str] | None = None,
        bash_commands: list[str] | None = None,
        assistant_text: str = "Done.",
        duration_ms: int = 5000,
    ) -> Self:
        """Add a simple turn with optional tool calls."""
        turn_entries: list[dict] = []
        ts_user = self._ts()

        # User entry
        turn_entries.append({
            "type": "user",
            "message": {"role": "user", "content": [{"type": "text", "text": user_text}]},
            "timestamp": ts_user,
            "sessionId": self.session_id,
            "version": "2.1.71",
            "gitBranch": self.git_branch,
            "slug": "test-slug",
        })

        # Build tool_use blocks + results
        tool_uses: list[dict] = []
        tool_results: list[dict] = []

        for fp in (file_reads or []):
            tid = self._tool_id()
            tool_uses.append({"type": "tool_use", "id": tid, "name": "Read", "input": {"file_path": fp}})
            tool_results.append(user_tool_result_entry(tid, f"contents of {fp}"))

        for fp in (file_writes or []):
            tid = self._tool_id()
            tool_uses.append({"type": "tool_use", "id": tid, "name": "Write", "input": {"file_path": fp, "content": "..."}})
            tool_results.append(user_tool_result_entry(tid, "ok"))

        for fp in (file_edits or []):
            tid = self._tool_id()
            tool_uses.append({"type": "tool_use", "id": tid, "name": "Edit", "input": {"file_path": fp, "old_string": "x", "new_string": "y"}})
            tool_results.append(user_tool_result_entry(tid, "ok"))

        for cmd in (bash_commands or []):
            tid = self._tool_id()
            tool_uses.append({"type": "tool_use", "id": tid, "name": "Bash", "input": {"command": cmd}})
            tool_results.append(user_tool_result_entry(tid, "ok"))

        if tool_uses:
            ts_asst1 = self._ts()
            turn_entries.append(assistant_entry(tool_uses, request_id=self._req_id(), timestamp=ts_asst1))
            turn_entries.extend(tool_results)

        # Final assistant text
        ts_asst_final = self._ts()
        turn_entries.append(assistant_entry(
            [{"type": "text", "text": assistant_text}],
            request_id=self._req_id(),
            timestamp=ts_asst_final,
        ))

        # Turn duration
        turn_entries.append(system_turn_duration(duration_ms))

        self._turns.append({"entries": turn_entries, "subagent_links": []})
        return self

    def add_subagent_turn(
        self,
        user_text: str,
        agent_description: str,
        subagent_file_reads: list[str] | None = None,
        subagent_file_writes: list[str] | None = None,
        parent_file_reads: list[str] | None = None,
        assistant_text: str = "Done.",
        duration_ms: int = 5000,
    ) -> Self:
        """Add a turn that launches a subagent.

        Creates parent entries (Agent tool_use + progress_agent_entry) AND
        stores subagent JSONL entries for writing to disk.
        """
        turn_entries: list[dict] = []
        ts_user = self._ts()

        # User entry
        turn_entries.append({
            "type": "user",
            "message": {"role": "user", "content": [{"type": "text", "text": user_text}]},
            "timestamp": ts_user,
            "sessionId": self.session_id,
            "version": "2.1.71",
            "gitBranch": self.git_branch,
            "slug": "test-slug",
        })

        # Parent file reads before agent call
        parent_tool_uses: list[dict] = []
        parent_tool_results: list[dict] = []
        for fp in (parent_file_reads or []):
            tid = self._tool_id()
            parent_tool_uses.append({"type": "tool_use", "id": tid, "name": "Read", "input": {"file_path": fp}})
            parent_tool_results.append(user_tool_result_entry(tid, f"contents of {fp}"))

        # Agent tool_use
        agent_tool_id = self._tool_id()
        agent_file_id = self._agent_id()

        parent_tool_uses.append({
            "type": "tool_use",
            "id": agent_tool_id,
            "name": "Agent",
            "input": {"description": agent_description, "prompt": f"Do: {agent_description}"},
        })

        if parent_tool_uses:
            ts_asst1 = self._ts()
            turn_entries.append(assistant_entry(parent_tool_uses, request_id=self._req_id(), timestamp=ts_asst1))
            turn_entries.extend(parent_tool_results)

        # Progress entry linking agent tool_use to subagent file
        turn_entries.append(progress_agent_entry(agent_tool_id, agent_file_id))

        # Agent tool result
        turn_entries.append(user_tool_result_entry(agent_tool_id, f"Agent completed: {agent_description}"))

        # Build subagent entries
        sa_entries: list[dict] = []
        sa_entries.append({
            "type": "user",
            "message": {"role": "user", "content": [{"type": "text", "text": f"Do: {agent_description}"}]},
            "timestamp": self._ts(),
            "sessionId": f"sa-{agent_file_id}",
        })

        sa_tool_uses: list[dict] = []
        sa_tool_results: list[dict] = []
        for fp in (subagent_file_reads or []):
            tid = self._tool_id()
            sa_tool_uses.append({"type": "tool_use", "id": tid, "name": "Read", "input": {"file_path": fp}})
            sa_tool_results.append(user_tool_result_entry(tid, f"contents of {fp}"))

        for fp in (subagent_file_writes or []):
            tid = self._tool_id()
            sa_tool_uses.append({"type": "tool_use", "id": tid, "name": "Write", "input": {"file_path": fp, "content": "..."}})
            sa_tool_results.append(user_tool_result_entry(tid, "ok"))

        if sa_tool_uses:
            sa_entries.append(assistant_entry(sa_tool_uses, request_id=self._req_id(), timestamp=self._ts()))
            sa_entries.extend(sa_tool_results)

        sa_entries.append(assistant_entry(
            [{"type": "text", "text": "Subagent done."}],
            request_id=self._req_id(),
            timestamp=self._ts(),
        ))

        self._subagents.append({"agent_id": agent_file_id, "entries": sa_entries})

        # Final assistant text
        ts_final = self._ts()
        turn_entries.append(assistant_entry(
            [{"type": "text", "text": assistant_text}],
            request_id=self._req_id(),
            timestamp=ts_final,
        ))
        turn_entries.append(system_turn_duration(duration_ms))

        self._turns.append({
            "entries": turn_entries,
            "subagent_links": [{"agent_id": agent_file_id, "entries": sa_entries}],
        })
        return self

    def build_entries(self) -> list[dict]:
        """Return the flat list of parent session entries."""
        entries: list[dict] = []
        for turn in self._turns:
            entries.extend(turn["entries"])
        return entries

    def write(self, base_dir: Path) -> Path:
        """Write session JSONL + subagent files to disk.

        Directory structure:
            base_dir/projects/<project_key>/<session_id>.jsonl
            base_dir/projects/<project_key>/<session_id>/subagents/agent-<id>.jsonl

        Returns the base_dir (for use as claude_dir).
        """
        project_dir = base_dir / "projects" / self.project_key
        project_dir.mkdir(parents=True, exist_ok=True)

        # Write parent session
        entries = self.build_entries()
        session_file = project_dir / f"{self.session_id}.jsonl"
        session_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

        # Write subagent files
        if self._subagents:
            sa_dir = project_dir / self.session_id / "subagents"
            sa_dir.mkdir(parents=True, exist_ok=True)
            for sa in self._subagents:
                sa_file = sa_dir / f"agent-{sa['agent_id']}.jsonl"
                sa_file.write_text("\n".join(json.dumps(e) for e in sa["entries"]) + "\n")

        return base_dir


class ClaudeDirBuilder:
    """Assemble a complete fake ~/.claude directory from multiple SessionBuilders.

    Example:
        claude_dir = (
            ClaudeDirBuilder(tmp_path)
            .add_session(SessionBuilder().add_turn("hi", file_reads=["/a.py"]))
            .add_session(SessionBuilder(session_id="sess-002").add_turn("bye"))
            .build()
        )
        cc = ClaudeCodeData(claude_dir=claude_dir)
    """

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self._builders: list[SessionBuilder] = []

    def add_session(self, builder: SessionBuilder) -> Self:
        self._builders.append(builder)
        return self

    def build(self) -> Path:
        """Write all sessions and return base_dir for use as claude_dir."""
        for builder in self._builders:
            builder.write(self.base_dir)
        return self.base_dir
