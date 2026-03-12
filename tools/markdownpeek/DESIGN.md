# markdownpeek — Design

## Purpose

A structural explorer for Markdown files, designed for AI agents. Lets agents understand document structure, navigate by heading, and extract sections without reading entire files.

## Architecture

```
src/markdownpeek/
    cli.py       — Argparse-based CLI with command dispatch
    parser.py    — Line-based Markdown parser (dataclasses + regex)
    help.py      — Tool descriptions and per-command help text
```

### Parser (`parser.py`)

Single-pass line scanner that produces a `ParsedMarkdown` object containing:

- **Headings** — ATX-only (`#` style), with level, text, line number, and computed section boundaries
- **Links** — inline links and images (`[text](url)` and `![alt](url)`)
- **Code blocks** — fenced blocks (`` ` `` and `~`), with language detection and proper nesting (longer fences contain shorter ones)
- **Front matter** — `---` delimited YAML at file start, recognized and skipped

Key design choices:

- **No dependencies.** Pure regex + line iteration. We only need structural elements, not rendered HTML.
- **ATX headings only.** Setext (underline) headings are rare in practice. Can add later if needed.
- **Code-block-aware.** Headings and links inside fenced code blocks are ignored. Nested fences (e.g. ```````` containing ``` ````) are handled by tracking fence character and length.
- **Section boundaries.** A section extends from its heading until the next heading of same or higher level (lower `#` count). This means `get` on an h2 includes its h3+ subsections. Computed in a second pass over the heading list.

### CLI (`cli.py`)

Commands are dispatched via argparse subparsers. Meta commands (`tool-description`, `tool-description-short`, `help`) are intercepted before argparse parsing to avoid rejection of unknown subcommand names.

All commands accept `-` for stdin input.

### Help (`help.py`)

Contains `TOOL_DESCRIPTION` (full agent-oriented text), `TOOL_DESCRIPTION_SHORT` (concise CLAUDE.md reference), and `COMMAND_HELP` (per-command detailed help). Separated from `cli.py` to keep the command implementations readable.

## Commands

| Command | Purpose | Key behavior |
|---------|---------|-------------|
| `toc` | Heading hierarchy | Line numbers + indentation by level |
| `peek` | Preview with truncation | First N lines of file or section, `--lines N` |
| `get` | Full section extraction | Includes subsections, `--no-line-numbers` |
| `stats` | File statistics | Lines, words, headings by level, code blocks by language, links, images, largest section |
| `links` | Link listing | `--images-only`, `--external-only` filters |
| `search` | Pattern search | Results grouped by section, `--regex`, `-C N` context |

## Section Addressing

Sections are found by case-insensitive substring match on heading text, first match wins. This is intentionally loose — agents can use partial names like "Install" instead of "Installation Guide".

## Data Flow

```
file/stdin → text → parse_markdown() → ParsedMarkdown → command handler → stdout
```

Every command reads the full file and parses it. No caching between commands — each invocation is independent. This is fine because the tool processes one file at a time and Markdown files are small relative to parse speed.

## What Was Considered and Rejected

- **Setext heading support** — Adds parser complexity for a format that's rare in practice. Can be added later.
- **Reference-style links** (`[text][ref]` with `[ref]: url` elsewhere) — Would require a two-pass link resolver. Inline links cover the vast majority of cases.
- **HTML block detection** — Would need an HTML parser. Out of scope for a structural Markdown tool.
- **Caching parsed results** — Not needed. Parse time is negligible for typical Markdown files, and the CLI is stateless.
- **Tree-structured output for toc** — Flat indented list is simpler to parse and sufficient for agents.
