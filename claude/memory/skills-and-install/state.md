# Branch: skills-and-install

## Goal
Add install CLI, Claude Code skills, and skill test harness to agentutils.

## Plan
See `plans/2026-03-19-skills-and-install-master.md`

## Current Status
All 3 milestones complete. Ready for human review.

### What was built:
1. **tools/agentutils-install/** — CLI with install, uninstall, install-skills, uninstall-skills, status commands
2. **skills/{gitro,lsrelated,markdownpeek}/SKILL.md** — Claude Code reference skills
3. **tests/skill_tests/run_skill_tests.py** — Test harness that verifies skills trigger tool usage

## Key Findings
- `uv tool install --from tools/<name> <name>` works for local installs
- Path dependencies (e.g. lsrelated → ccdata) resolve correctly
- Tools: gitro (no deps), lsrelated (typer, rich, orjson, ccdata), markdownpeek (no deps)
