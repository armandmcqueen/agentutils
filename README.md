# agentutils

A monorepo of small, focused CLI tools designed for AI agents. Each tool is independently installable via `uv`.

## Tools

| Tool | Description |
|------|-------------|
| `markdownpeek` | Structural explorer for Markdown files |

## Usage

Run any tool directly with `uv`:

```bash
uv run --directory tools/<name> <name> <args>
```

Every tool exposes self-describing commands:

```bash
# Full agent-oriented description
uv run --directory tools/<name> <name> tool-description

# Concise version suitable for CLAUDE.md
uv run --directory tools/<name> <name> tool-description-short
```

## Development

Run tests for a specific tool:

```bash
uv run --directory tools/<name> pytest
```

## Repo Layout

```
tools/     — Installable CLI tools (each has its own pyproject.toml)
libs/      — Shared libraries referenced as path dependencies
```
