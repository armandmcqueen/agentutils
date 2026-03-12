# gitro — Design

## Problem

AI agents exploring codebases can accidentally mutate git state — committing work-in-progress, pushing to remote, resetting branches, etc. A read-only git wrapper prevents this class of accidents entirely.

## Approach: Fail-Closed Allowlist

Commands are validated against an explicit allowlist of known read-only git subcommands. Unknown or unrecognized commands are rejected. This is fail-closed — new or obscure git commands are blocked by default.

### Alternatives Considered

- **Blocklist (block known mutations)**: Fail-open. New git commands or aliases would be allowed by default, which is the wrong safety posture.
- **`--dry-run` injection**: Not all git commands support `--dry-run`, and behavior varies. Would require per-command logic anyway.

## Architecture

```
cli.py          # Entry point: meta-commands, validation, subprocess
policy.py       # Allowlist, conditional rules, validate()
help.py         # Tool descriptions and help text
```

### Validation Flow

1. Parse and skip global git flags (`-C`, `--no-pager`, etc.)
2. Extract the subcommand (first non-flag argument)
3. Check against three categories:
   - **Unconditionally allowed**: Any flags are fine (e.g. `log`, `diff`, `status`)
   - **Conditionally allowed**: Specific flags/sub-subcommands are restricted (e.g. `branch` allows listing but blocks `-d`)
   - **Explicitly blocked**: Clear error message explaining why (e.g. `commit`, `push`)
4. Unknown subcommands are rejected with a generic message

### Conditional Rules

Five subcommands have nuanced policies:

- **`branch`**: Listing flags allowed; delete/move/copy/upstream flags blocked
- **`tag`**: Listing allowed; create/delete/sign/force blocked
- **`stash`**: `list` and `show` allowed; bare stash (=push), pop, drop, etc. blocked
- **`remote`**: bare, `-v`, `show`, `get-url` allowed; add, remove, rename, etc. blocked
- **`config`**: Read-only flags (`--get`, `--list`, etc.) and bare key lookup allowed; mutating flags blocked

### Key Decisions

- **`fetch` is blocked**: While it only downloads, it modifies local refs and could surprise agents. `ls-remote` covers the read-only use case.
- **Git aliases are rejected**: They're not in the allowlist. This is intentional — aliases could map to arbitrary commands.
- **No argparse for git args**: Git arguments are opaque passthrough. Only meta-commands (`tool-description`, `allowed`, `help`) are parsed by gitro.
- **Global flags**: Recognized and skipped during subcommand extraction, then passed through to git unchanged.

## Testing

- `test_policy.py`: 146 tests covering all allowed, blocked, and conditional cases plus edge cases
- `test_cli.py`: 12 tests covering meta-commands and mocked subprocess passthrough
