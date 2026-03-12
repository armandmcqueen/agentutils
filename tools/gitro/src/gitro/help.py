"""Help text and tool descriptions for gitro."""

TOOL_DESCRIPTION_SHORT = """\
## `gitro`

Read-only git wrapper for AI agents. Validates commands against an allowlist,
then passes through to `git`. Blocks commits, pushes, resets, and other mutations.

```bash
gitro <any read-only git command>   # e.g. gitro log --oneline -10
gitro allowed                       # list all allowed subcommands
```"""

TOOL_DESCRIPTION = """\
# gitro — Read-only Git for Agents

A safety wrapper around git that blocks mutating operations. Use `gitro`
exactly like `git`, but only read-only commands are allowed.

## Why

AI agents exploring a codebase can accidentally mutate git state — committing
WIP, pushing to remote, resetting branches, etc. `gitro` is a drop-in `git`
replacement that validates every command against an allowlist before execution.
Unknown or mutating commands are rejected with a clear error.

## Usage

```bash
gitro <git args>           # Passes through to git if allowed
gitro log --oneline -10    # Works — log is read-only
gitro diff HEAD~3          # Works — diff is read-only
gitro commit -m "oops"     # BLOCKED — commit is mutating
gitro push                 # BLOCKED — push is mutating
```

## Allowed Commands

### Unconditionally allowed (any flags)
`log`, `diff`, `show`, `status`, `blame`, `shortlog`, `describe`,
`rev-parse`, `rev-list`, `cat-file`, `ls-files`, `ls-tree`, `ls-remote`,
`name-rev`, `for-each-ref`, `grep`, `reflog`, `diff-tree`, `diff-files`,
`diff-index`, `merge-base`, `count-objects`, `fsck`, `verify-commit`,
`verify-tag`, `cherry`, `whatchanged`, `range-diff`, `version`, `help`

### Conditionally allowed
- `branch` — listing only (no `-d`, `-D`, `-m`, `-M`, etc.)
- `tag` — listing only (no `-d`, `-a`, `-s`, `-f`, etc.)
- `stash` — `list` and `show` only (no bare stash, pop, drop, etc.)
- `remote` — bare, `-v`, `show`, `get-url` only (no add, remove, etc.)
- `config` — read-only flags only (`--get`, `--list`, `-l`, etc.)

### Blocked
All mutating commands: `commit`, `push`, `pull`, `fetch`, `merge`, `rebase`,
`reset`, `checkout`, `switch`, `restore`, `add`, `rm`, `mv`, `clean`, `init`,
`clone`, `cherry-pick`, `revert`, `bisect`, and more.

## Meta-commands

```bash
gitro tool-description        # This help text
gitro tool-description-short  # Concise version for CLAUDE.md
gitro allowed                 # List all allowed subcommands with notes
gitro help                    # Same as tool-description
```

## Global git flags

Global flags like `-C <path>`, `--git-dir=<path>`, `--no-pager`, etc. are
recognized and skipped when extracting the subcommand. Unknown flags before
the subcommand are rejected.

## Limitations

- **Git aliases are not supported.** Aliases are not in the allowlist and will
  be rejected. Use the underlying git command directly.
- **`fetch` is blocked.** While technically read-oriented, it modifies local
  refs. Use `ls-remote` instead for remote info.

## Workflow

1. Use `gitro` as a drop-in replacement for `git` in agent tooling
2. If a command is blocked, the error message explains why
3. Run `gitro allowed` to see what's available"""

COMMAND_HELP = {
    "tool-description": "Print the full agent-oriented tool description",
    "tool-description-short": "Print a concise tool description for CLAUDE.md",
    "allowed": "List all allowed git subcommands with restriction notes",
    "help": "Print help (same as tool-description, or help <command>)",
}


def format_allowed_commands() -> str:
    """Format the allowed commands list for the 'allowed' meta-command."""
    from gitro.policy import (
        UNCONDITIONALLY_ALLOWED,
        _CONDITIONAL_VALIDATORS,
    )

    lines = ["Allowed git subcommands:\n"]

    lines.append("  Unconditionally allowed (any flags):")
    for cmd in sorted(UNCONDITIONALLY_ALLOWED):
        lines.append(f"    {cmd}")

    lines.append("")
    lines.append("  Conditionally allowed (some flags restricted):")
    notes = {
        "branch": "listing only — no delete, move, copy, or upstream changes",
        "tag": "listing only — no create, delete, sign, or force",
        "stash": "'list' and 'show' only — no push, pop, drop, apply, clear",
        "remote": "bare, -v, show, get-url only — no add, remove, rename, set-url",
        "config": "read-only: --get, --list, -l, --get-all, --get-regexp, or bare key lookup",
    }
    for cmd in sorted(_CONDITIONAL_VALIDATORS):
        lines.append(f"    {cmd} — {notes.get(cmd, 'restricted')}")

    return "\n".join(lines)
