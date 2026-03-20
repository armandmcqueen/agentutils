---
name: gitro
description: Use when running git commands to prevent accidental mutations, or when needing a safe read-only git interface in agent context
---

# gitro — Read-only Git for Agents

Use `gitro` instead of `git` for all read-only operations. It blocks mutating commands (commit, push, reset, checkout, etc.) and passes read-only ones through to git.

## Usage

```bash
gitro log --oneline -10
gitro diff HEAD~3
gitro status
gitro blame src/main.py
```

Mutating commands are rejected with a clear error:

```bash
gitro commit -m "oops"   # BLOCKED
gitro push               # BLOCKED
```

## When to Use

- **Always** for read-only git operations in agent context — prevents accidental mutations
- Use `gitro allowed` to see the full list of permitted commands
- Use `gitro tool-description` for detailed docs

## Key Details

- Drop-in replacement for `git` — same syntax
- `branch`, `tag`, `stash`, `remote`, `config` are allowed in read-only modes only
- `fetch` is blocked (modifies local refs) — use `ls-remote` for remote info
- Git aliases are not supported
