# ccdata

Structured access to Claude Code session JSONL data. Parses session files from `~/.claude/projects/` into typed Python objects for analysis, exploration, and tooling.

## Installation

```bash
uv pip install -e libs/ccdata
```

## Quick Start

```python
from ccdata import ClaudeCodeData

cc = ClaudeCodeData()                          # all projects
cc = ClaudeCodeData(project="armand-dev")       # substring filter

# Explore
print(cc.summary())
print(cc.session_ids)

# Load sessions
s = cc.session("abc123-...")
for t in s.turns:
    print(f"[Turn {t.index}] {t.user_text[:80]}")
    for tc in t.tool_calls:
        print(f"  {tc.name}: {tc.summary}")

# DataFrames (requires pandas)
df = cc.sessions_df()
df.groupby("git_branch")["output_tokens"].sum()
```

## Key Concepts

- **Session**: A complete Claude Code conversation (one JSONL file)
- **Turn**: A user prompt + all assistant responses before the next prompt
- **AssistantResponse**: A single API response (a turn can have multiple)
- **ToolCall**: A tool invocation with its result
- **Compaction**: Detected context window compaction events

## API

See `ClaudeCodeData.help()` for the full API reference, or the [DESIGN.md](DESIGN.md) for architecture details.

## `ccdata.testing` — Test Fixture Builders

The `ccdata.testing` module provides reusable builders for constructing fake Claude Code session data on disk. Use it in ccdata's own tests or in downstream tools (e.g. lsrelated) for integration testing.

```python
from ccdata.testing import SessionBuilder, ClaudeDirBuilder

# Build a session with turns and subagents
builder = (
    SessionBuilder(session_id="sess-001")
    .add_turn("Read files", file_reads=["/src/main.py", "/src/util.py"])
    .add_subagent_turn("Research", "find files",
                       subagent_file_reads=["/lib/helper.py"])
)

# Write to a tmp directory and use as claude_dir
claude_dir = ClaudeDirBuilder(tmp_path).add_session(builder).build()
cc = ClaudeCodeData(claude_dir=claude_dir)
```

**Entry builders**: `user_text_entry()`, `assistant_entry()`, `system_turn_duration()`, `progress_agent_entry()`, etc. — low-level JSONL entry constructors.

**SessionBuilder**: Declarative session construction with `add_turn()` and `add_subagent_turn()`. Auto-generates timestamps, tool IDs, and request IDs. Writes subagent JSONL files alongside the parent session.

**ClaudeDirBuilder**: Assembles a complete fake `~/.claude` directory from multiple `SessionBuilder` instances.

## Testing

```bash
uv run --directory libs/ccdata pytest
```

All tests use synthetic JSONL fixtures — no real session data needed.
