"""markdownpeek CLI — Structural explorer for Markdown files."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter

from markdownpeek.help import COMMAND_HELP, TOOL_DESCRIPTION, TOOL_DESCRIPTION_SHORT
from markdownpeek.parser import find_section, get_section_lines, parse_markdown


def _read_input(path: str) -> str:
    """Read from file path or stdin if path is '-'."""
    if path == "-":
        return sys.stdin.read()
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)
    except IsADirectoryError:
        print(f"Is a directory: {path}", file=sys.stderr)
        sys.exit(1)


def _cmd_toc(args: argparse.Namespace) -> int:
    text = _read_input(args.file)
    parsed = parse_markdown(text)

    if not parsed.headings:
        print("(no headings found)")
        return 0

    for h in parsed.headings:
        indent = "  " * (h.level - 1)
        print(f"{h.line_num:>5}: {indent}{h.text}")
    return 0


def _cmd_peek(args: argparse.Namespace) -> int:
    text = _read_input(args.file)
    parsed = parse_markdown(text)
    max_lines = args.lines

    if args.section:
        heading = find_section(parsed, args.section)
        if heading is None:
            print(f"No section matching '{args.section}'", file=sys.stderr)
            return 1
        lines = get_section_lines(parsed, heading)
        start_num = heading.line_num
    else:
        lines = parsed.lines
        start_num = 1

    truncated = len(lines) > max_lines
    show_lines = lines[:max_lines]

    for i, line in enumerate(show_lines):
        print(f"{start_num + i:>5}: {line}")

    if truncated:
        remaining = len(lines) - max_lines
        print(f"  ... ({remaining} more lines)")

    return 0


def _cmd_get(args: argparse.Namespace) -> int:
    text = _read_input(args.file)
    parsed = parse_markdown(text)

    heading = find_section(parsed, args.section)
    if heading is None:
        print(f"No section matching '{args.section}'", file=sys.stderr)
        return 1

    lines = get_section_lines(parsed, heading)
    start_num = heading.line_num

    for i, line in enumerate(lines):
        if args.no_line_numbers:
            print(line)
        else:
            print(f"{start_num + i:>5}: {line}")

    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    text = _read_input(args.file)
    parsed = parse_markdown(text)

    total_lines = len(parsed.lines)
    total_words = sum(len(line.split()) for line in parsed.lines)

    print(f"Lines: {total_lines}")
    print(f"Words: {total_words}")

    # Headings by level
    if parsed.headings:
        level_counts = Counter(h.level for h in parsed.headings)
        print(f"Headings: {len(parsed.headings)}")
        for level in sorted(level_counts):
            print(f"  h{level}: {level_counts[level]}")
    else:
        print("Headings: 0")

    # Code blocks by language
    if parsed.code_blocks:
        lang_counts = Counter(cb.language or "(none)" for cb in parsed.code_blocks)
        print(f"Code blocks: {len(parsed.code_blocks)}")
        for lang in sorted(lang_counts):
            print(f"  {lang}: {lang_counts[lang]}")
    else:
        print("Code blocks: 0")

    # Links and images
    images = [l for l in parsed.links if l.is_image]
    non_images = [l for l in parsed.links if not l.is_image]
    print(f"Links: {len(non_images)}")
    print(f"Images: {len(images)}")

    # Front matter
    if parsed.front_matter:
        fm_lines = parsed.front_matter.line_end - parsed.front_matter.line_start + 1
        print(f"Front matter: {fm_lines} lines")

    # Largest section
    if parsed.headings:
        largest = max(parsed.headings, key=lambda h: h.content_end - h.line_num)
        section_lines = largest.content_end - largest.line_num + 1
        print(f"Largest section: \"{largest.text}\" ({section_lines} lines)")

    return 0


def _cmd_links(args: argparse.Namespace) -> int:
    text = _read_input(args.file)
    parsed = parse_markdown(text)

    links = parsed.links

    if args.images_only:
        links = [l for l in links if l.is_image]
    elif args.external_only:
        links = [l for l in links if l.url.startswith(("http://", "https://"))]

    if not links:
        print("(no links found)")
        return 0

    for link in links:
        prefix = "IMG" if link.is_image else "LNK"
        print(f"{link.line_num:>5}: [{prefix}] {link.text} -> {link.url}")

    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    text = _read_input(args.file)
    parsed = parse_markdown(text)
    pattern = args.pattern
    context = args.context

    if args.regex:
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            print(f"Invalid regex: {e}", file=sys.stderr)
            return 1
        match_fn = lambda line: regex.search(line) is not None
    else:
        pattern_lower = pattern.lower()
        match_fn = lambda line: pattern_lower in line.lower()

    # Find all matching line numbers (0-based)
    matches = [i for i, line in enumerate(parsed.lines) if match_fn(line)]

    if not matches:
        print("(no matches)")
        return 0

    # Group matches by section
    def _find_section_for_line(line_idx: int) -> str:
        """Find the most specific (deepest) heading containing a line (0-based)."""
        line_num = line_idx + 1  # 1-based
        containing = None
        for h in parsed.headings:
            if h.line_num <= line_num <= h.content_end:
                # Prefer deeper (more specific) headings
                if containing is None or h.level > containing.level:
                    containing = h
        return containing.text if containing else "(top level)"

    current_section = None
    printed_lines: set[int] = set()

    for match_idx in matches:
        section = _find_section_for_line(match_idx)
        if section != current_section:
            if current_section is not None:
                print()
            print(f"── {section} ──")
            current_section = section

        start = max(0, match_idx - context)
        end = min(len(parsed.lines), match_idx + context + 1)

        for i in range(start, end):
            if i not in printed_lines:
                marker = ">" if i == match_idx else " "
                print(f"{marker}{i + 1:>5}: {parsed.lines[i]}")
                printed_lines.add(i)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="markdownpeek",
        description="Structural explorer for Markdown files",
        add_help=False,
    )
    subparsers = parser.add_subparsers(dest="command")

    # toc
    p_toc = subparsers.add_parser("toc", help="Show heading hierarchy")
    p_toc.add_argument("file")

    # peek
    p_peek = subparsers.add_parser("peek", help="Preview file or section")
    p_peek.add_argument("file")
    p_peek.add_argument("section", nargs="?", default=None)
    p_peek.add_argument("--lines", type=int, default=20)

    # get
    p_get = subparsers.add_parser("get", help="Extract full section")
    p_get.add_argument("file")
    p_get.add_argument("section")
    p_get.add_argument("--no-line-numbers", action="store_true")

    # stats
    p_stats = subparsers.add_parser("stats", help="File statistics")
    p_stats.add_argument("file")

    # links
    p_links = subparsers.add_parser("links", help="List all links")
    p_links.add_argument("file")
    p_links.add_argument("--images-only", action="store_true")
    p_links.add_argument("--external-only", action="store_true")

    # search
    p_search = subparsers.add_parser("search", help="Search with section context")
    p_search.add_argument("file")
    p_search.add_argument("pattern")
    p_search.add_argument("--regex", action="store_true")
    p_search.add_argument("-C", dest="context", type=int, default=0)

    # Handle meta commands before argparse (which rejects unknown subcommands)
    raw = argv if argv is not None else sys.argv[1:]
    if not raw or raw[0] == "help":
        subcmd = raw[1] if len(raw) > 1 else None
        if subcmd and subcmd in COMMAND_HELP:
            print(COMMAND_HELP[subcmd], end="")
            return 0
        elif subcmd:
            print(f"Unknown command: {subcmd}", file=sys.stderr)
            return 1
        print(TOOL_DESCRIPTION, end="")
        return 0
    if raw[0] == "tool-description":
        print(TOOL_DESCRIPTION, end="")
        return 0
    if raw[0] == "tool-description-short":
        print(TOOL_DESCRIPTION_SHORT, end="")
        return 0

    valid_commands = {"toc", "peek", "get", "stats", "links", "search"}
    if raw[0] not in valid_commands:
        print(f"Unknown command: {raw[0]}", file=sys.stderr)
        print("Run 'markdownpeek help' for usage.", file=sys.stderr)
        return 1

    parsed = parser.parse_args(argv)
    command = parsed.command

    if command is None:
        print(f"Unknown command: {raw[0]}", file=sys.stderr)
        print("Run 'markdownpeek help' for usage.", file=sys.stderr)
        return 1

    dispatch = {
        "toc": _cmd_toc,
        "peek": _cmd_peek,
        "get": _cmd_get,
        "stats": _cmd_stats,
        "links": _cmd_links,
        "search": _cmd_search,
    }

    return dispatch[command](parsed)


if __name__ == "__main__":
    sys.exit(main())
