---
name: markdownpeek
description: Use when working with large Markdown files and you need structure, specific sections, or search without reading the entire file
---

# markdownpeek — Structural Markdown Explorer

Navigate large Markdown files by structure. Understand headings, extract sections, and search — without reading the entire file.

## Usage

```bash
markdownpeek toc file.md                  # heading hierarchy with line numbers
markdownpeek peek file.md "Setup"         # preview first 20 lines of a section
markdownpeek get file.md "Setup"          # extract full section content
markdownpeek search file.md "pattern"     # search with section context
markdownpeek stats file.md                # file statistics
markdownpeek links file.md                # list all links
```

## When to Use

- **Large Markdown files** (README, docs, specs) — get structure before reading
- **Need a specific section** — extract it directly instead of reading the whole file
- **Searching within Markdown** — results include section context
- For small files, just use `Read` directly
- Run `markdownpeek tool-description` for full docs

## Typical Workflow

1. `markdownpeek toc file.md` — understand the structure
2. `markdownpeek peek file.md "Section"` — preview what you need
3. `markdownpeek get file.md "Section"` — extract it
