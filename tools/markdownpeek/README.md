# markdownpeek

Structural explorer for Markdown files, designed for AI agents. Like `jsonpeek` but for Markdown — understand structure before diving into content.

## Usage

```bash
# Heading hierarchy with line numbers
uv run --directory tools/markdownpeek markdownpeek toc README.md

# Preview first 20 lines (or a section)
uv run --directory tools/markdownpeek markdownpeek peek README.md
uv run --directory tools/markdownpeek markdownpeek peek README.md "Usage"

# Extract full section content
uv run --directory tools/markdownpeek markdownpeek get README.md "Usage"

# File statistics
uv run --directory tools/markdownpeek markdownpeek stats README.md

# List all links
uv run --directory tools/markdownpeek markdownpeek links README.md

# Search with section context
uv run --directory tools/markdownpeek markdownpeek search README.md "pattern"
```

All commands accept `-` to read from stdin.

## Agent Integration

```bash
# Full description for agent consumption
markdownpeek tool-description

# Short reference for CLAUDE.md
markdownpeek tool-description-short

# Per-command help
markdownpeek help toc
```

## Design

- No dependencies — line-based regex parser
- ATX headings only (`#` style)
- Sections extend until the next heading of same or higher level
- Front matter (`---` delimited) is recognized and skipped
- Headings inside code blocks are ignored
