# textplate

A markdown-based templating tool. Write `.textplate.md` files with special `text::` links, then run `textplate press` to resolve all references into plain markdown.

## Install

```bash
# Via agentutils installer
agentutils install

# Or standalone
uv tool install --from tools/textplate textplate
```

## Quick Start

Create source files — just plain text or markdown:

```
# greeting.txt
Hello from a reusable snippet!
```

Create a template (`doc.textplate.md`):

```markdown
# My Document

[](text::./greeting.txt)

[](text::./notes.md#intro)
```

Press it:

```bash
textplate press doc.textplate.md           # writes doc.md
textplate press doc.textplate.md --stdout  # prints to stdout
```

Or watch it and re-press automatically:

```bash
textplate watch doc.textplate.md --every 5s
```

## Syntax

```markdown
[](text::./path/to/file.txt)           # include entire file
[](text::./path/to/file.md#section)    # include section body (heading excluded)
[](text::./path/to/file.md#section!)   # include section with its heading
```

- `text::` prefix marks a template reference
- `#fragment` uses GitHub-style heading slugs (lowercase, spaces to hyphens)
- A section includes everything under a heading until the next heading of the same or higher level
- By default the heading line is excluded; append `!` to include it
- Output naming: `foo.textplate.md` → `foo.md`. Otherwise `foo.md` → `foo.filled.md`
- Strict mode: if any reference can't be resolved, the command fails with no partial output

## Testing

```bash
uv run --directory tools/textplate pytest
```

## Demo

See [`demo/`](demo/) for a working example:

```bash
uv run --directory tools/textplate textplate press demo/docs.textplate.md --stdout
```
