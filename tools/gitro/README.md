# gitro

Read-only git wrapper for AI agents. Validates every git command against an allowlist before execution — mutating operations are blocked with a clear error message.

## Installation

```bash
uv run --directory tools/gitro gitro <args>
```

## Usage

Use `gitro` exactly like `git`:

```bash
gitro log --oneline -10       # allowed
gitro diff HEAD~3              # allowed
gitro status                   # allowed
gitro branch -a                # allowed (listing)
gitro commit -m "oops"         # BLOCKED
gitro push                     # BLOCKED
```

## Meta-commands

```bash
gitro tool-description         # Full agent-oriented help
gitro tool-description-short   # Concise version for CLAUDE.md
gitro allowed                  # List all allowed subcommands
gitro help                     # Same as tool-description
```

## Testing

```bash
uv run --directory tools/gitro pytest
```

See [DESIGN.md](DESIGN.md) for architecture details.
