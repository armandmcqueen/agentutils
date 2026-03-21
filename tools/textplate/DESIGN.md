# textplate — Design

## Overview

textplate resolves `text::` links in markdown templates into plain markdown output. It's designed for composing documentation from reusable snippets.

## Architecture

The code is split into four modules:

### `core.py` — Template Processing Logic

Pure logic with no CLI or UI concerns:

1. **Regex patterns** — `LINK_PATTERN` matches `[label](text::source)` links. `HEADING_PATTERN` matches markdown headings. `FENCE_PATTERN` tracks fenced code blocks.
2. **`extract_section()`** — Finds a heading by GitHub-style slug, captures content until the next heading of the same or higher level. Correctly skips headings inside fenced code blocks via `_update_fence_state()`.
3. **`resolve_reference()`** — Takes a source string and base directory, determines if it's a whole-file or section reference, reads and returns content.
4. **`process_template()`** — Orchestrates the pipeline: find all links → resolve all references → validate (strict mode) → replace in reverse order.
5. **`press_file()`** — Runs the full press operation: read template, process, add header, write output.
6. **`compute_output_path()`** — Naming convention logic.

### `watch.py` — Watch Loop

Contains the continuous re-pressing loop, progress bar rendering, and interval parsing. Owns its own `Console()` instance for rich output.

### `cli.py` — Typer Application

Thin wrappers that handle argument validation and delegate to core/watch. Includes `tool-description` and `tool-description-short` meta-commands.

### `help.py` — Agent-Oriented Descriptions

`TOOL_DESCRIPTION`, `TOOL_DESCRIPTION_SHORT`, and `COMMAND_HELP` constants for agent discovery.

## Key Decisions

### Strict mode (no partial output)
All references are resolved before any replacements happen. If any reference fails, the entire command fails with a clear error listing all failures.

### Reverse-order replacement
Replacements are applied from last match to first, so string positions remain valid throughout. No offset tracking needed.

### Output path convention
- `foo.textplate.md` → `foo.md` (clean removal of `.textplate` infix)
- `other.md` → `other.filled.md` (safe: won't overwrite the input)

### No recursion
Resolved content containing `text::` links is NOT recursively resolved. This prevents infinite loops and keeps behavior predictable.

### Watch error handling
By default, `watch` logs errors and continues. The `--strict` flag makes errors fatal. Useful during development when source files may be temporarily broken.

## Section Addressing

Sections use standard markdown headings with GitHub-style slugs:

- `## My Section` → `#my-section`
- Slugs are lowercase, spaces become hyphens, punctuation is stripped
- A section includes all content under a heading until the next heading of the **same or higher level**
- Sub-headings are included in the parent section
- Heading line excluded by default; append `!` to include it

Source files are just normal markdown — no custom markers needed.
