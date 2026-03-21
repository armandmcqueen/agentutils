---
name: textplate
description: Use when working with .textplate.md files, composing documentation from reusable markdown snippets, or resolving text:: references
---

# textplate — Markdown Templating Tool

Compose documents from reusable markdown snippets using `text::` link syntax. Resolve all references into plain markdown output.

## Usage

```bash
textplate press file.textplate.md              # resolve and write output
textplate press file.textplate.md --stdout     # print to stdout
textplate watch file.textplate.md --every 5s   # continuous mode
```

## Syntax

```markdown
[](text::./path/to/file.txt)            # include entire file
[](text::./path/to/file.md#section)     # include section (heading excluded)
[](text::./path/to/file.md#section!)    # include section with heading
```

Sections are addressed by GitHub-style heading slugs (`## My Section` → `#my-section`).

## When to Use

- **Composing documentation** from modular source files
- **Building READMEs** that pull content from multiple locations
- **Any document** with `text::` references that need resolving
- Run `textplate tool-description` for full docs

## Typical Workflow

1. Create a `.textplate.md` file with `text::` links to source content
2. `textplate press template.textplate.md` to generate output
3. Output: `foo.textplate.md` → `foo.md`, `other.md` → `other.filled.md`
