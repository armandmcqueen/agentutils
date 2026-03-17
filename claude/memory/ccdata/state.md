# ccdata branch — Current State

## What exists
- `libs/ccdata/` — Library for parsing Claude Code session data (JSONL logs, compaction detection, subagent merging)
- `libs/ccdata/src/ccdata/testing.py` — Shared test fixtures: entry builders, SessionBuilder, ClaudeDirBuilder
- `tools/lsrelated/` — CLI tool to find files frequently accessed together in Claude Code sessions
- `README.md` — Updated with lsrelated entry in tools table

## Test counts
- ccdata: 101 passing
- lsrelated: 35 passing

## Status
All code committed but NOT merged to main. Review identified issues to fix before merge (see log).
