"""Tool descriptions and command help text."""

TOOL_DESCRIPTION = """\
markdownpeek — Structural explorer for Markdown files.

Designed for AI agents working with large Markdown documents. Understand
structure, navigate by heading, and extract sections without reading the
entire file.

COMMANDS:

  markdownpeek toc <file>
    Show heading hierarchy as a table of contents with line numbers.
    Gives you the structural overview to decide what to read next.

  markdownpeek peek <file> [section]
    Preview first 20 lines of the file or a specific section (truncated).
    Use --lines N to change the preview length.

  markdownpeek get <file> <section>
    Extract full content of a section (heading + body until next
    same-or-higher-level heading). Use --no-line-numbers for clean output.

  markdownpeek stats <file>
    File statistics: line count, word count, heading count by level,
    code block count by language, link count, image count, largest section.

  markdownpeek links <file>
    List all links with line numbers, text, and URL.
    Use --images-only for images, --external-only for external URLs.

  markdownpeek search <file> <pattern>
    Search within the file, returning matches grouped by section context.
    Use --regex for regex patterns, -C N for context lines.

SELF-DESCRIPTION:

  markdownpeek tool-description
    Print this full description.

  markdownpeek tool-description-short
    Print a concise description suitable for CLAUDE.md.

  markdownpeek help [command]
    Detailed help for a specific command.

STDIN: All commands accept `-` to read from stdin.

TYPICAL WORKFLOW:
  1. markdownpeek toc file.md              — understand the structure
  2. markdownpeek peek file.md "Setup"     — preview a section
  3. markdownpeek get file.md "Setup"      — extract what you need
"""

TOOL_DESCRIPTION_SHORT = """\
### `markdownpeek`

Structural explorer for Markdown files. Use markdownpeek instead of reading
entire Markdown files when you only need structure or specific sections.

```
markdownpeek toc <file>           — heading hierarchy with line numbers
markdownpeek peek <file> [section] — preview a section (truncated)
markdownpeek get <file> <section>  — extract full section content
markdownpeek stats <file>          — file statistics
markdownpeek links <file>          — list all links
markdownpeek search <file> <pat>   — search with section context
```

SETUP: markdownpeek tool-description >> ~/.claude/CLAUDE.md
"""

COMMAND_HELP = {
    "toc": """\
markdownpeek toc <file>

Show heading hierarchy as a table of contents with line numbers.

Output format:
  <line_num>: <indent><heading text>

Indentation reflects heading level (## = 2 spaces, ### = 4 spaces, etc.).

Examples:
  markdownpeek toc README.md
  cat file.md | markdownpeek toc -
""",
    "peek": """\
markdownpeek peek <file> [section]

Preview the first N lines of the file or a specific section.

Arguments:
  file      Path to markdown file, or - for stdin
  section   Optional heading text to match (case-insensitive substring)

Options:
  --lines N   Number of lines to show (default: 20)

If a section is specified, shows lines starting from that heading.
If content exceeds --lines, a truncation notice is appended.

Examples:
  markdownpeek peek README.md
  markdownpeek peek README.md "Installation"
  markdownpeek peek README.md "Install" --lines 50
""",
    "get": """\
markdownpeek get <file> <section>

Extract the full content of a section including the heading line and all
content until the next same-or-higher-level heading.

Arguments:
  file      Path to markdown file, or - for stdin
  section   Heading text to match (case-insensitive substring)

Options:
  --no-line-numbers   Omit line number prefixes from output

Examples:
  markdownpeek get README.md "Installation"
  markdownpeek get README.md "install" --no-line-numbers
""",
    "stats": """\
markdownpeek stats <file>

Show file statistics including line count, word count, heading counts
by level, code block counts by language, link and image counts, and
the largest section by line count.

Examples:
  markdownpeek stats README.md
  cat file.md | markdownpeek stats -
""",
    "links": """\
markdownpeek links <file>

List all links found in the file with line numbers, text, and URL.

Options:
  --images-only     Show only image links
  --external-only   Show only external (http/https) links

Examples:
  markdownpeek links README.md
  markdownpeek links README.md --images-only
  markdownpeek links README.md --external-only
""",
    "search": """\
markdownpeek search <file> <pattern>

Search for a pattern in the markdown file. Results are grouped by the
section they appear in.

Arguments:
  file      Path to markdown file, or - for stdin
  pattern   Text to search for (literal by default)

Options:
  --regex   Treat pattern as a regular expression
  -C N      Show N context lines around each match (default: 0)

Examples:
  markdownpeek search README.md "installation"
  markdownpeek search README.md "def \\w+" --regex
  markdownpeek search README.md "error" -C 2
""",
    "tool-description": "Prints the full agent-oriented tool description.",
    "tool-description-short": "Prints a concise description suitable for CLAUDE.md.",
}
