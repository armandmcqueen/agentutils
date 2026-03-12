# agentutils — Repo Conventions

## Monorepo Layout

- `tools/<name>/` — Independently installable CLI tools. Each has its own `pyproject.toml` with hatchling build system.
- `libs/<name>/` — Shared libraries as installable packages. Tools reference them as path dependencies in `pyproject.toml`.

## Running Tools

```bash
uv run --directory tools/<name> <name> <args>
```

## Testing

```bash
uv run --directory tools/<name> pytest
```

Tests must not require external infrastructure. Mock external services.

## Tool Description Convention

Every tool MUST implement two subcommands:

- `tool-description` — Full agent-oriented description (detailed usage, examples, workflow guidance). This is what an agent reads to learn how to use the tool.
- `tool-description-short` — Concise version (a few lines) suitable for pasting into a CLAUDE.md file as a quick reference.

These are the primary discovery mechanism for agents. The full description should be comprehensive enough that an agent can use the tool effectively without additional documentation.

## Adding a New Tool

1. Create `tools/<name>/` with the standard structure:
   ```
   tools/<name>/
   ├── pyproject.toml
   ├── README.md
   ├── src/<name>/
   │   ├── __init__.py
   │   └── cli.py
   └── tests/
       └── test_cli.py
   ```
2. Implement `tool-description` and `tool-description-short` subcommands.
3. Add entry point in `pyproject.toml` under `[project.scripts]`.
4. Add the tool to the table in the repo `README.md`.
