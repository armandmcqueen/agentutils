# ccdata — Design Document

## Purpose

ccdata is a library for parsing and querying Claude Code session data. It reads JSONL session files from `~/.claude/projects/` and provides structured Python objects for analysis.

## Data Model

```
ClaudeCodeData
  └─ Session
       ├─ metadata: session_id, project_key, version, git_branch, slug
       ├─ file_path: Path to the JSONL file
       └─ Turn[]
            ├─ index, user_text, timestamp, duration_ms
            ├─ compaction_before: Compaction | None
            └─ AssistantResponse[]
                 ├─ request_id, model, stop_reason, timestamp
                 ├─ usage: Usage
                 ├─ text_blocks: TextBlock[]
                 ├─ tool_calls: ToolCall[]
                 └─ thinking_blocks: ThinkingBlock[]
```

## Module Structure

The entire library lives in `src/ccdata/__init__.py` (~500 lines). The code is tightly coupled parsing logic where splitting into modules would add complexity without benefit. Import pattern: `from ccdata import ClaudeCodeData`.

## Key Design Decisions

### Single Module
The library is ~500 lines with tightly coupled dataclasses and parsing logic. Splitting into separate files (models.py, parsing.py, etc.) would just scatter related code across files without any real encapsulation benefit.

### orjson Optional
Uses `try/except` to optionally use orjson for ~2.7x faster JSON parsing. Falls back to stdlib json. No hard dependency declared — consumers like lsrelated can declare it.

### pandas Optional
DataFrame methods (`sessions_df()`, `turns_df()`, etc.) import pandas lazily. Tests use `pytest.importorskip("pandas")`. pandas is in dev dependencies only.

### merge_subagents Parameter
`parse_session()` accepts `merge_subagents=True` to control whether subagent tool calls are merged into parent turns. This replaces the original monkey-patching approach used by lsrelated's `--no-subagents` flag. `ClaudeCodeData` also accepts this parameter and passes it through.

### Compaction Detection
Compaction is detected by monitoring total context tokens (input + cache_read + cache_create) across consecutive assistant entries. A >20% drop indicates compaction. The heuristic: `total < prev_total * 0.8`.

### Turn Detection
A new turn starts when a `user` entry has text content. User entries with only `tool_result` blocks belong to the current turn (they're tool responses, not new prompts).

## JSONL Format

Session data lives at `~/.claude/projects/<project-key>/<session-id>.jsonl`. Subagent data lives at `<session-id>/subagents/agent-<agentId>.jsonl`. See the entry type documentation in the source for the full format specification.

## Testing

96+ tests using synthetic JSONL fixtures. Tests cover all dataclasses, parsing helpers, edge cases, compaction detection, session/turn properties, and all 5 DataFrame builders.
