# lsrelated

Find files that are frequently accessed together in Claude Code sessions. Useful for understanding file relationships and gathering context for AI coding tools.

## Installation

```bash
uv run --directory tools/lsrelated lsrelated --help
```

## Usage

```bash
# Find files related to a specific file
lsrelated related src/lib/types.ts
lsrelated related types.ts -n 20        # partial match, more results

# See most-connected files in a project
lsrelated top -p myproject

# Exclude subagent tool calls
lsrelated related types.ts --no-subagents

# Show all matching files for ambiguous queries
lsrelated related types.ts -m
```

## How It Works

Builds an **undirected co-access graph** from Claude Code session data. When two files are Read/Write/Edited in the same turn, they get an edge. Edge weight = number of turns where both files appear. Subagent tool calls are merged into parent turns by default.

## Commands

| Command | Description |
|---------|-------------|
| `related <file>` | Show top related files for a given file |
| `top` | Show files with the most co-access connections |
| `tool-description` | Full agent-oriented description |
| `tool-description-short` | Concise version for CLAUDE.md |

## Testing

```bash
uv run --directory tools/lsrelated pytest
```
