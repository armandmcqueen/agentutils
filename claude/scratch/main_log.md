# main branch log

## 2026-03-12T00:00:00Z — Port ccdata + lsrelated into agentutils

### Milestone 1: ccdata library
- Created `libs/ccdata/` with pyproject.toml, src/ccdata/__init__.py
- Faithful port of ccdata.py from claude-code/customtools/
- Added `merge_subagents` parameter to `parse_session()` and `ClaudeCodeData`
- Ported all 96 original tests + 2 new tests for merge_subagents=False
- 98 tests passing

### Milestone 2: lsrelated CLI
- Created `tools/lsrelated/` with proper package structure
- Split into cli.py (Typer commands) and graph.py (logic)
- Replaced sys.path hack with proper path dependency on ccdata
- Replaced monkey-patching with merge_subagents=False parameter
- Added tool-description and tool-description-short commands
- 30 tests passing (25 graph + 5 CLI)

### Milestone 3: Docs + repo integration
- Wrote README.md and DESIGN.md for both libs/ccdata and tools/lsrelated
- Added lsrelated to repo README.md tools table
