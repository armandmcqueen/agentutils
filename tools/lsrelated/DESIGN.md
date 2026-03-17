# lsrelated — Design Document

## Purpose

CLI tool that finds files frequently accessed together in Claude Code sessions. It builds a co-access graph and lets you query file relationships.

## Architecture

```
cli.py    — Typer CLI with commands: related, top, tool-description, tool-description-short
graph.py  — Graph building, file matching, and display prefix logic
```

The tool depends on the `ccdata` library (path dependency in `../../libs/ccdata`) for session parsing.

## Key Algorithms

### Graph Building (`build_undirected_graph`)
- Extracts file paths from Read/Write/Edit tool calls in each turn
- Dedupes consecutive repeats (same file read twice in a row)
- Skips self-edges (same file appearing non-consecutively in a turn)
- Creates canonical sorted pairs: `(min(a,b), max(a,b))`
- Dedupes pairs within each turn (same pair counted once per turn)
- Accumulates weights across turns and sessions

### File Matching (`find_file`)
Resolves partial file names to full paths:
1. Exact match
2. Suffix match (e.g. `types.ts` matches `/foo/bar/types.ts`)
3. Substring match
4. If multiple matches, picks the one with highest access count

### Display Prefix (`find_display_prefix`)
Finds the longest directory prefix covering >50% of files. This is better than `os.path.commonprefix` because session data includes files outside the project (e.g. `~/.claude/plans/`) which would make the common prefix empty.

## Design Decisions

### Clean Subagent Toggle
Uses `merge_subagents=False` parameter on `ClaudeCodeData` instead of the original monkey-patching approach. This was an improvement identified during the port.

### Undirected Graph
Uses undirected edges (A and B in same turn = single edge) rather than directed (A before B = edge from A to B). Direction adds noise without clear value for the "related files" use case.

### Turn-Level Granularity
Co-access is measured at the turn level, not the session level. A turn represents a coherent unit of work. Session-level would create too many false connections between unrelated tasks.

### Consecutive Dedup
Files are deduped within a turn only for consecutive repeats (`[A, B, A]` keeps both A's). Re-reading a file after reading others suggests stronger relationship. Self-edges are explicitly filtered.

## Dependencies

- `ccdata` — Session data parsing (path dependency)
- `typer` — CLI framework
- `rich` — Table output
- `orjson` — Fast JSON parsing (used by ccdata)
