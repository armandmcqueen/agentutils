"""
Claude Code session data library.

Provides structured access to Claude Code session JSONL data.
Designed for interactive exploration in notebooks, scripts, or REPL.

Usage:
    from ccdata import ClaudeCodeData
    cc = ClaudeCodeData()                          # all projects
    cc = ClaudeCodeData(project="armand-dev")       # substring match on project name

See ClaudeCodeData.help() for full API documentation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TYPE_CHECKING

try:
    import orjson as _json

    def _loads(s: str | bytes) -> Any:
        return _json.loads(s)

    def _dumps(obj: Any, **kw: Any) -> str:
        return _json.dumps(obj).decode()

except ImportError:
    import json as _json  # type: ignore[no-redef]

    def _loads(s: str | bytes) -> Any:  # type: ignore[misc]
        return _json.loads(s)

    def _dumps(obj: Any, **kw: Any) -> str:  # type: ignore[misc]
        return _json.dumps(obj, **kw)

if TYPE_CHECKING:
    import pandas as pd


# -- Defaults --

CLAUDE_DIR = Path.home() / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"


# -- Data Classes --


@dataclass
class Usage:
    """Token usage for a single API request."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    service_tier: str | None = None

    @property
    def total_context(self) -> int:
        return self.input_tokens + self.cache_read_input_tokens + self.cache_creation_input_tokens

    @classmethod
    def from_raw(cls, raw: dict[str, Any] | None) -> Usage:
        if not raw:
            return cls()
        return cls(
            input_tokens=raw.get("input_tokens", 0),
            output_tokens=raw.get("output_tokens", 0),
            cache_read_input_tokens=raw.get("cache_read_input_tokens", 0),
            cache_creation_input_tokens=raw.get("cache_creation_input_tokens", 0),
            service_tier=raw.get("service_tier"),
        )


@dataclass
class ToolCall:
    """A tool invocation by the assistant."""
    name: str
    tool_use_id: str
    input: dict[str, Any]
    result: str | None = None
    is_error: bool = False

    @property
    def summary(self) -> str:
        """Short human-readable summary of what this tool call did."""
        inp = self.input
        if self.name in ("Read", "Write", "Edit"):
            return inp.get("file_path", "")
        if self.name == "Bash":
            return (inp.get("command", "") or "")[:120]
        if self.name in ("Glob", "Grep"):
            return inp.get("pattern", "")
        if self.name == "Agent":
            s = inp.get("description", "") or inp.get("prompt", "") or ""
            return s[:120]
        if self.name == "Skill":
            return inp.get("skill", "")
        return ""


@dataclass
class TextBlock:
    """A text content block from the assistant."""
    text: str


@dataclass
class ThinkingBlock:
    """A thinking content block (content is redacted in session logs)."""
    signature: str = ""


@dataclass
class AssistantResponse:
    """One assistant API response within a turn."""
    request_id: str | None
    model: str | None
    stop_reason: str | None
    usage: Usage
    text_blocks: list[TextBlock]
    tool_calls: list[ToolCall]
    thinking_blocks: list[ThinkingBlock]
    timestamp: str | None

    @property
    def text(self) -> str:
        """Combined text output from this response."""
        return "\n".join(b.text for b in self.text_blocks)

    @property
    def tool_names(self) -> list[str]:
        return [tc.name for tc in self.tool_calls]


@dataclass
class Compaction:
    """A context compaction event."""
    pre_tokens: int
    post_tokens: int
    ratio: float
    timestamp: str | None = None


@dataclass
class Turn:
    """A single human->assistant turn in a session."""
    index: int
    user_text: str
    timestamp: str | None
    responses: list[AssistantResponse] = field(default_factory=list)
    duration_ms: int | None = None
    compaction_before: Compaction | None = None

    @property
    def text(self) -> str:
        """All assistant text across all responses in this turn."""
        return "\n".join(r.text for r in self.responses if r.text)

    @property
    def tool_calls(self) -> list[ToolCall]:
        """All tool calls across all responses in this turn."""
        return [tc for r in self.responses for tc in r.tool_calls]

    @property
    def tool_names(self) -> list[str]:
        return [tc.name for tc in self.tool_calls]

    @property
    def usage(self) -> Usage:
        """Aggregated usage across all responses in this turn."""
        return Usage(
            input_tokens=sum(r.usage.input_tokens for r in self.responses),
            output_tokens=sum(r.usage.output_tokens for r in self.responses),
            cache_read_input_tokens=sum(r.usage.cache_read_input_tokens for r in self.responses),
            cache_creation_input_tokens=sum(r.usage.cache_creation_input_tokens for r in self.responses),
        )

    def __repr__(self) -> str:
        preview = self.user_text[:60].replace("\n", " ")
        n_tools = len(self.tool_calls)
        return f"Turn({self.index}, {n_tools} tools, {preview!r})"


@dataclass
class Session:
    """A complete Claude Code session."""
    session_id: str
    project_key: str
    file_path: Path
    turns: list[Turn]
    version: str | None = None
    git_branch: str | None = None
    slug: str | None = None
    raw_entry_count: int = 0

    @property
    def project_name(self) -> str:
        """Human-readable project name derived from the project key."""
        return self.project_key.strip("-").replace("-", "/")

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def first_timestamp(self) -> str | None:
        for t in self.turns:
            if t.timestamp:
                return t.timestamp
        return None

    @property
    def last_timestamp(self) -> str | None:
        for t in reversed(self.turns):
            if t.timestamp:
                return t.timestamp
        return None

    @property
    def total_tool_calls(self) -> int:
        return sum(len(t.tool_calls) for t in self.turns)

    @property
    def tool_counts(self) -> dict[str, int]:
        """Count of each tool used across the session."""
        counts: dict[str, int] = {}
        for t in self.turns:
            for tc in t.tool_calls:
                counts[tc.name] = counts.get(tc.name, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    @property
    def total_usage(self) -> Usage:
        return Usage(
            input_tokens=sum(t.usage.input_tokens for t in self.turns),
            output_tokens=sum(t.usage.output_tokens for t in self.turns),
            cache_read_input_tokens=sum(t.usage.cache_read_input_tokens for t in self.turns),
            cache_creation_input_tokens=sum(t.usage.cache_creation_input_tokens for t in self.turns),
        )

    @property
    def compactions(self) -> list[Compaction]:
        return [t.compaction_before for t in self.turns if t.compaction_before]

    @property
    def duration_s(self) -> float | None:
        """Total session duration in seconds from timestamps, or None."""
        first = self.first_timestamp
        last = self.last_timestamp
        if not first or not last:
            return None
        try:
            t0 = datetime.fromisoformat(first.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(last.replace("Z", "+00:00"))
            return (t1 - t0).total_seconds()
        except Exception:
            return None

    def __repr__(self) -> str:
        branch = f" [{self.git_branch}]" if self.git_branch else ""
        ts = self.first_timestamp or "?"
        return f"Session({self.session_id[:8]}..{branch}, {self.turn_count} turns, {ts})"


# -- Parsing --


def _is_user_text_entry(entry: dict) -> bool:
    if entry.get("type") != "user":
        return False
    msg = entry.get("message", {})
    content = msg.get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list) and content:
        return content[0].get("type") == "text"
    return False


def _get_user_text(entry: dict) -> str:
    msg = entry.get("message", {})
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content if b.get("type") == "text"
        )
    return ""


def _collect_tool_results(entries: list[dict]) -> dict[str, tuple[str, bool]]:
    """Build map of tool_use_id -> (result_text, is_error) from user entries."""
    results: dict[str, tuple[str, bool]] = {}
    for entry in entries:
        if entry.get("type") != "user":
            continue
        content = entry.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") != "tool_result":
                continue
            tool_use_id = block.get("tool_use_id", "")
            rc = block.get("content")
            if isinstance(rc, str):
                text = rc
            elif isinstance(rc, list):
                text = "\n".join(
                    x.get("text", f"[{x.get('type', '?')}]")
                    for x in rc
                    if isinstance(x, dict)
                )
            else:
                text = ""
            results[tool_use_id] = (text, bool(block.get("is_error", False)))
    return results


def _parse_subagent_tool_calls(sa_path: Path) -> list[ToolCall]:
    """Parse a subagent JSONL file and extract its tool calls."""
    tool_calls = []
    entries = []
    for line in sa_path.read_bytes().split(b"\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(_loads(line))
        except (ValueError, TypeError):
            continue

    tool_results = _collect_tool_results(entries)

    for entry in entries:
        if entry.get("type") != "assistant":
            continue
        content = entry.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "tool_use":
                tid = block.get("id", "")
                result_text, is_error = tool_results.get(tid, (None, False))
                tool_calls.append(ToolCall(
                    name=block.get("name", ""),
                    tool_use_id=tid,
                    input=block.get("input", {}),
                    result=result_text,
                    is_error=is_error,
                ))
    return tool_calls


def _build_agent_id_map(entries: list[dict]) -> dict[str, str]:
    """Build map of Agent tool_use_id -> subagent file ID from progress entries.

    Progress entries with data.type=agent_progress have:
      parentToolUseID -> the Agent tool_use block id
      data.agentId -> the subagent ID (used in filename agent-{id}.jsonl)
    """
    mapping: dict[str, str] = {}
    for entry in entries:
        if entry.get("type") != "progress":
            continue
        data = entry.get("data", {})
        if data.get("type") != "agent_progress":
            continue
        parent_tid = entry.get("parentToolUseID")
        agent_id = data.get("agentId")
        if parent_tid and agent_id and parent_tid not in mapping:
            mapping[parent_tid] = agent_id
    return mapping


def parse_session(file_path: Path, *, merge_subagents: bool = True) -> Session:
    """Parse a session JSONL file into a structured Session object.

    Args:
        file_path: Path to the session JSONL file.
        merge_subagents: If True (default), merge subagent tool calls into
            the parent turn that launched them. If False, skip subagent merging
            entirely.
    """
    raw = file_path.read_bytes()
    entries = []
    for line in raw.split(b"\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(_loads(line))
        except (ValueError, TypeError):
            continue

    # Extract metadata from first entries that have them
    version = None
    git_branch = None
    slug = None
    session_id = file_path.stem
    project_key = file_path.parent.name

    for e in entries:
        if not version and e.get("version"):
            version = e["version"]
        if not git_branch and e.get("gitBranch"):
            git_branch = e["gitBranch"]
        if not slug and e.get("slug"):
            slug = e["slug"]
        if version and git_branch and slug:
            break

    # Collect tool results for matching
    tool_results = _collect_tool_results(entries)

    # Detect compaction via context drops
    prev_context: dict[str, int] = {}  # agent_key -> last total context
    compaction_events: list[tuple[int, Compaction]] = []  # (entry_index, compaction)

    for i, entry in enumerate(entries):
        if entry.get("type") != "assistant":
            continue
        msg = entry.get("message", {})
        usage_raw = msg.get("usage", {})
        input_t = usage_raw.get("input_tokens", 0)
        cache_read = usage_raw.get("cache_read_input_tokens", 0)
        cache_create = usage_raw.get("cache_creation_input_tokens", 0)
        total = input_t + cache_read + cache_create
        if total <= 0:
            continue
        key = "__parent__"
        prev = prev_context.get(key, 0)
        if prev > 0 and total < prev * 0.8:
            compaction_events.append((i, Compaction(
                pre_tokens=prev,
                post_tokens=total,
                ratio=total / prev if prev else 0,
                timestamp=entry.get("timestamp"),
            )))
        prev_context[key] = total

    # Build turns
    turns: list[Turn] = []
    current_turn: Turn | None = None

    # Index compaction events by entry index for quick lookup
    compaction_by_entry: dict[int, Compaction] = {idx: c for idx, c in compaction_events}

    # Find the next compaction event after each user entry
    compaction_entry_indices = sorted(compaction_by_entry.keys())

    for i, entry in enumerate(entries):
        etype = entry.get("type")

        if _is_user_text_entry(entry):
            # Check if any compaction event comes between previous assistant
            # entries and this user entry -- attach it to this turn
            compaction = None
            for ci in compaction_entry_indices:
                # Compaction detected at assistant entry ci; if it's the first
                # assistant response after the last user entry but before this one,
                # it belongs to this turn
                if current_turn is not None and ci > 0:
                    # Find if ci is between the last user text and this one
                    last_user_idx = None
                    for j in range(i - 1, -1, -1):
                        if _is_user_text_entry(entries[j]):
                            last_user_idx = j
                            break
                    if last_user_idx is not None and last_user_idx < ci < i:
                        compaction = compaction_by_entry.pop(ci)
                        compaction_entry_indices.remove(ci)
                        break

            current_turn = Turn(
                index=len(turns),
                user_text=_get_user_text(entry),
                timestamp=entry.get("timestamp"),
                compaction_before=compaction,
            )
            turns.append(current_turn)
            continue

        # Skip non-user, non-assistant, non-system
        if etype == "assistant" and current_turn is not None:
            msg = entry.get("message", {})
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue

            text_blocks = []
            tool_calls = []
            thinking_blocks = []

            for block in content:
                bt = block.get("type")
                if bt == "text":
                    text_blocks.append(TextBlock(text=block.get("text", "")))
                elif bt == "tool_use":
                    tid = block.get("id", "")
                    result_text, is_error = tool_results.get(tid, (None, False))
                    tool_calls.append(ToolCall(
                        name=block.get("name", ""),
                        tool_use_id=tid,
                        input=block.get("input", {}),
                        result=result_text,
                        is_error=is_error,
                    ))
                elif bt == "thinking":
                    thinking_blocks.append(ThinkingBlock(
                        signature=block.get("signature", ""),
                    ))

            usage = Usage.from_raw(msg.get("usage"))
            current_turn.responses.append(AssistantResponse(
                request_id=entry.get("requestId"),
                model=msg.get("model"),
                stop_reason=msg.get("stop_reason"),
                usage=usage,
                text_blocks=text_blocks,
                tool_calls=tool_calls,
                thinking_blocks=thinking_blocks,
                timestamp=entry.get("timestamp"),
            ))

        elif etype == "system" and entry.get("subtype") == "turn_duration" and current_turn is not None:
            current_turn.duration_ms = entry.get("durationMs")

    # Attach any remaining compaction events to turns
    for ci, comp in sorted(compaction_by_entry.items()):
        for turn in turns:
            if turn.compaction_before is None and turn.responses:
                turn.compaction_before = comp
                break

    # Merge subagent tool calls into parent turns
    if merge_subagents:
        agent_id_map = _build_agent_id_map(entries)
        sa_dir = file_path.parent / session_id / "subagents"

        if agent_id_map and sa_dir.exists():
            for turn in turns:
                for response in turn.responses:
                    for tc in response.tool_calls:
                        if tc.name != "Agent":
                            continue
                        sa_file_id = agent_id_map.get(tc.tool_use_id)
                        if not sa_file_id:
                            continue
                        sa_path = sa_dir / f"agent-{sa_file_id}.jsonl"
                        if not sa_path.exists():
                            continue
                        sa_tool_calls = _parse_subagent_tool_calls(sa_path)
                        idx = response.tool_calls.index(tc)
                        response.tool_calls[idx + 1:idx + 1] = sa_tool_calls

    return Session(
        session_id=session_id,
        project_key=project_key,
        file_path=file_path,
        turns=turns,
        version=version,
        git_branch=git_branch,
        slug=slug,
        raw_entry_count=len(entries),
    )


# -- Main Class --


class ClaudeCodeData:
    """
    Structured access to Claude Code session data.

    Lazily loads session data -- session files are only parsed when accessed.

    Args:
        project: Optional substring filter for project name (e.g. "armand-dev").
        claude_dir: Path to ~/.claude (default: ~/.claude).
        merge_subagents: If True (default), merge subagent tool calls into parent turns.
    """

    def __init__(
        self,
        project: str | None = None,
        claude_dir: Path | str | None = None,
        merge_subagents: bool = True,
    ):
        self._claude_dir = Path(claude_dir) if claude_dir else CLAUDE_DIR
        self._projects_dir = self._claude_dir / "projects"
        self._project_filter = project
        self._merge_subagents = merge_subagents
        self._session_cache: dict[str, Session] = {}

        # Discover project directories
        self._project_dirs: dict[str, Path] = {}
        if self._projects_dir.exists():
            for d in sorted(self._projects_dir.iterdir()):
                if not d.is_dir():
                    continue
                key = d.name
                if project and project.lower() not in key.lower():
                    continue
                self._project_dirs[key] = d

    @property
    def project_keys(self) -> list[str]:
        """All matching project keys."""
        return list(self._project_dirs.keys())

    @property
    def projects(self) -> dict[str, list[str]]:
        """Map of project_key -> list of session IDs."""
        result: dict[str, list[str]] = {}
        for key, path in self._project_dirs.items():
            session_ids = [
                f.stem for f in sorted(path.glob("*.jsonl"))
            ]
            result[key] = session_ids
        return result

    @property
    def session_ids(self) -> list[str]:
        """All session IDs across all matching projects."""
        ids = []
        for key, path in self._project_dirs.items():
            ids.extend(f.stem for f in sorted(path.glob("*.jsonl")))
        return ids

    @property
    def session_count(self) -> int:
        return len(self.session_ids)

    def session(self, session_id: str) -> Session:
        """Load and return a parsed Session by ID. Results are cached."""
        if session_id in self._session_cache:
            return self._session_cache[session_id]

        # Find the file
        for key, path in self._project_dirs.items():
            fp = path / f"{session_id}.jsonl"
            if fp.exists():
                sess = parse_session(fp, merge_subagents=self._merge_subagents)
                self._session_cache[session_id] = sess
                return sess

        raise FileNotFoundError(f"Session {session_id} not found in any project")

    def sessions(self, limit: int | None = None) -> list[Session]:
        """Load all sessions. Pass limit to restrict count (useful for testing)."""
        ids = self.session_ids
        if limit:
            ids = ids[:limit]
        return [self.session(sid) for sid in ids]

    def sessions_by_branch(self) -> dict[str | None, list[Session]]:
        """Group all sessions by git branch."""
        by_branch: dict[str | None, list[Session]] = {}
        for sess in self.sessions():
            by_branch.setdefault(sess.git_branch, []).append(sess)
        return by_branch

    # -- DataFrame builders --

    def sessions_df(self, limit: int | None = None) -> "pd.DataFrame":
        """One row per session."""
        import pandas as pd
        rows = []
        for s in self.sessions(limit=limit):
            u = s.total_usage
            rows.append({
                "session_id": s.session_id,
                "project_key": s.project_key,
                "git_branch": s.git_branch,
                "version": s.version,
                "slug": s.slug,
                "turn_count": s.turn_count,
                "total_tool_calls": s.total_tool_calls,
                "compaction_count": len(s.compactions),
                "first_timestamp": s.first_timestamp,
                "last_timestamp": s.last_timestamp,
                "duration_s": s.duration_s,
                "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens,
                "cache_read_tokens": u.cache_read_input_tokens,
                "cache_create_tokens": u.cache_creation_input_tokens,
                "total_context": u.total_context,
                "raw_entry_count": s.raw_entry_count,
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            df["first_timestamp"] = pd.to_datetime(df["first_timestamp"], utc=True, errors="coerce")
            df["last_timestamp"] = pd.to_datetime(df["last_timestamp"], utc=True, errors="coerce")
        return df

    def turns_df(self, limit: int | None = None) -> "pd.DataFrame":
        """One row per turn across all sessions."""
        import pandas as pd
        rows = []
        for s in self.sessions(limit=limit):
            for t in s.turns:
                u = t.usage
                rows.append({
                    "session_id": s.session_id,
                    "git_branch": s.git_branch,
                    "turn_index": t.index,
                    "timestamp": t.timestamp,
                    "user_text": t.user_text,
                    "user_text_len": len(t.user_text),
                    "assistant_text_len": len(t.text),
                    "response_count": len(t.responses),
                    "tool_call_count": len(t.tool_calls),
                    "tool_names": t.tool_names,
                    "duration_ms": t.duration_ms,
                    "had_compaction": t.compaction_before is not None,
                    "input_tokens": u.input_tokens,
                    "output_tokens": u.output_tokens,
                    "cache_read_tokens": u.cache_read_input_tokens,
                    "cache_create_tokens": u.cache_creation_input_tokens,
                })
        df = pd.DataFrame(rows)
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        return df

    def tool_calls_df(self, limit: int | None = None) -> "pd.DataFrame":
        """One row per tool call across all sessions."""
        import pandas as pd
        rows = []
        for s in self.sessions(limit=limit):
            for t in s.turns:
                for tc in t.tool_calls:
                    rows.append({
                        "session_id": s.session_id,
                        "git_branch": s.git_branch,
                        "turn_index": t.index,
                        "tool_name": tc.name,
                        "summary": tc.summary,
                        "is_error": tc.is_error,
                        "has_result": tc.result is not None,
                        "result_len": len(tc.result) if tc.result else 0,
                        "input_keys": sorted(tc.input.keys()),
                    })
        return pd.DataFrame(rows)

    def responses_df(self, limit: int | None = None) -> "pd.DataFrame":
        """One row per assistant API response across all sessions."""
        import pandas as pd
        rows = []
        for s in self.sessions(limit=limit):
            for t in s.turns:
                for ri, r in enumerate(t.responses):
                    rows.append({
                        "session_id": s.session_id,
                        "git_branch": s.git_branch,
                        "turn_index": t.index,
                        "response_index": ri,
                        "request_id": r.request_id,
                        "model": r.model,
                        "stop_reason": r.stop_reason,
                        "timestamp": r.timestamp,
                        "text_block_count": len(r.text_blocks),
                        "tool_call_count": len(r.tool_calls),
                        "thinking_block_count": len(r.thinking_blocks),
                        "text_len": len(r.text),
                        "input_tokens": r.usage.input_tokens,
                        "output_tokens": r.usage.output_tokens,
                        "cache_read_tokens": r.usage.cache_read_input_tokens,
                        "cache_create_tokens": r.usage.cache_creation_input_tokens,
                        "total_context": r.usage.total_context,
                    })
        df = pd.DataFrame(rows)
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        return df

    def compactions_df(self, limit: int | None = None) -> "pd.DataFrame":
        """One row per compaction event across all sessions."""
        import pandas as pd
        rows = []
        for s in self.sessions(limit=limit):
            for t in s.turns:
                if t.compaction_before:
                    c = t.compaction_before
                    rows.append({
                        "session_id": s.session_id,
                        "git_branch": s.git_branch,
                        "turn_index": t.index,
                        "timestamp": c.timestamp,
                        "pre_tokens": c.pre_tokens,
                        "post_tokens": c.post_tokens,
                        "ratio": c.ratio,
                    })
        df = pd.DataFrame(rows)
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        return df

    def summary(self) -> str:
        """Quick text summary of the dataset."""
        lines = [f"ClaudeCodeData: {len(self._project_dirs)} project(s)"]
        for key in self._project_dirs:
            sids = self.projects[key]
            lines.append(f"  {key}: {len(sids)} sessions")
        return "\n".join(lines)

    def __repr__(self) -> str:
        filt = f", project={self._project_filter!r}" if self._project_filter else ""
        return f"ClaudeCodeData({self.session_count} sessions{filt})"

    @staticmethod
    def help() -> str:
        """Print full API documentation."""
        doc = """
ClaudeCodeData API
==================

SETUP
-----
  from ccdata import ClaudeCodeData
  cc = ClaudeCodeData()                        # all projects
  cc = ClaudeCodeData(project="armand-dev")     # filter by project name
  cc = ClaudeCodeData(merge_subagents=False)    # skip subagent merging

DISCOVERY
---------
  cc.project_keys          -> list of project key strings
  cc.projects              -> dict: project_key -> [session_id, ...]
  cc.session_ids           -> flat list of all session IDs
  cc.session_count         -> int
  cc.summary()             -> quick text overview

LOADING SESSIONS
----------------
  s = cc.session("abc123-...")   -> Session (cached after first load)
  all_s = cc.sessions()          -> list[Session] (loads all)
  cc.sessions(limit=5)           -> load first 5 only
  cc.sessions_by_branch()        -> dict: branch -> [Session, ...]

SESSION OBJECT
--------------
  s.session_id, s.project_key, s.project_name, s.version, s.git_branch, s.slug
  s.turns -> list[Turn], s.turn_count -> int
  s.first_timestamp, s.last_timestamp, s.duration_s
  s.total_tool_calls, s.tool_counts, s.total_usage, s.compactions, s.raw_entry_count

TURN OBJECT
-----------
  t.index, t.user_text, t.timestamp, t.responses -> list[AssistantResponse]
  t.text, t.tool_calls, t.tool_names, t.usage, t.duration_ms, t.compaction_before

ASSISTANT RESPONSE
------------------
  r.request_id, r.model, r.stop_reason, r.usage, r.timestamp
  r.text_blocks, r.tool_calls, r.thinking_blocks, r.text, r.tool_names

TOOL CALL
---------
  tc.name, tc.tool_use_id, tc.input, tc.result, tc.is_error, tc.summary

DATAFRAMES (requires pandas)
-----------------------------
  cc.sessions_df(), cc.turns_df(), cc.tool_calls_df(), cc.responses_df(), cc.compactions_df()
  All accept optional limit=N parameter.
"""
        print(doc)
        return doc
