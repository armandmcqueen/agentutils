---
name: lsrelated
description: Use when exploring an unfamiliar codebase, investigating which files are coupled, or deciding what else to read after opening a file
---

# lsrelated — Find Related Files

Finds files frequently accessed together in Claude Code sessions. Built from a co-access graph — when two files are read/edited in the same turn, they get an edge.

## Usage

```bash
lsrelated related <file>           # top related files
lsrelated related <file> -n 20     # more results
lsrelated top                      # most-connected files overall
lsrelated top -p myproject         # scoped to a project
```

File matching is flexible — suffix and substring matching work:

```bash
lsrelated related types.ts         # matches src/lib/types.ts
```

## When to Use

- **Exploring unfamiliar code** — find what files are typically touched together
- **After opening a file** — discover related files you should also read
- **Understanding coupling** — see which files form a logical unit
- Run `lsrelated tool-description` for full docs
