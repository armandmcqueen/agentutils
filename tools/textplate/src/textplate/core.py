"""Core template processing logic for textplate."""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# Matches [label](text::source) — single line only, no newlines in source
LINK_PATTERN = re.compile(r"\[([^\]]*)\]\(text::([^)\n]+)\)")

# Matches markdown headings: # Heading, ## Heading, etc.
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# Matches fenced code block delimiters (``` or ~~~, optionally with language)
FENCE_PATTERN = re.compile(r"^(`{3,}|~{3,})")


class ResolveError(Exception):
    """Raised when a text:: reference cannot be resolved."""


def slugify(text: str) -> str:
    """Convert heading text to a GitHub-style slug.

    Lowercase, replace spaces with hyphens, strip non-alphanumeric (except hyphens).
    """
    slug = text.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    return slug


def _update_fence_state(line: str, current_fence: str | None) -> str | None:
    """Track fenced code block state.

    Returns the current fence delimiter string if inside a fence, None if outside.
    A closing fence must use the same character (` or ~) and be at least as long
    as the opening fence.
    """
    m = FENCE_PATTERN.match(line.strip())
    if not m:
        return current_fence
    delimiter = m.group(1)
    if current_fence is None:
        # Opening a new fence
        return delimiter
    # We're inside a fence — check if this closes it
    # Must be same char type and at least as long
    if delimiter[0] == current_fence[0] and len(delimiter) >= len(current_fence):
        return None
    return current_fence


def extract_section(
    content: str, section_slug: str, source_path: str, *, include_heading: bool = False
) -> str:
    """Extract a section from markdown by heading slug.

    Finds the heading whose slug matches section_slug, then captures all content
    until the next heading of the same or higher level (fewer or equal #'s).
    If include_heading is True, the heading line itself is included in the output.
    """
    lines = content.splitlines(keepends=True)
    target_level = None
    heading_line_idx = None
    fence_marker: str | None = None  # tracks the opening fence delimiter

    # Find the matching heading (skip fenced code blocks)
    for i, line in enumerate(lines):
        fence_marker = _update_fence_state(line, fence_marker)
        if fence_marker is not None:
            continue
        m = HEADING_PATTERN.match(line)
        if m and slugify(m.group(2)) == section_slug:
            target_level = len(m.group(1))
            heading_line_idx = i
            break

    if heading_line_idx is None:
        raise ResolveError(
            f"Section '{section_slug}' not found in {source_path}"
        )

    # Capture until next heading of same or higher level (skip fenced code blocks)
    body_start = heading_line_idx + 1
    captured: list[str] = []
    fence_marker = None
    for line in lines[body_start:]:
        fence_marker = _update_fence_state(line, fence_marker)
        if fence_marker is None:
            m = HEADING_PATTERN.match(line)
            if m and len(m.group(1)) <= target_level:
                break
        captured.append(line)

    if include_heading:
        captured.insert(0, lines[heading_line_idx])

    text = "".join(captured)
    return text.strip("\n")


def resolve_reference(source: str, base_dir: Path) -> str:
    """Resolve a text:: source reference to its content.

    Supports:
    - Local file paths (relative to base_dir)
    - Local file paths with #section fragment
    """
    # Split fragment if present
    fragment = None
    if "#" in source and not source.startswith("http"):
        source, fragment = source.rsplit("#", 1)
        if not fragment:
            raise ResolveError(f"Empty section fragment in reference: {source}#")

    # Resolve file path
    file_path = (base_dir / source).resolve()

    if not file_path.is_file():
        raise ResolveError(f"File not found: {file_path}")

    content = file_path.read_text()

    if fragment:
        include_heading = fragment.endswith("!")
        slug = fragment[:-1] if include_heading else fragment
        return extract_section(content, slug, str(file_path), include_heading=include_heading)

    return content.strip("\n")


def process_template(template_content: str, base_dir: Path) -> str:
    """Process a template string, resolving all text:: references.

    Raises ResolveError if any reference cannot be resolved.
    All references are validated before any replacements are made (strict mode).
    """
    matches = list(LINK_PATTERN.finditer(template_content))
    if not matches:
        return template_content

    # Resolve all references first (strict: fail before any replacement)
    resolutions: list[tuple[re.Match, str]] = []
    errors: list[str] = []

    for match in matches:
        source = match.group(2)
        try:
            resolved = resolve_reference(source, base_dir)
            resolutions.append((match, resolved))
        except ResolveError as e:
            errors.append(str(e))

    if errors:
        raise ResolveError(
            "Failed to resolve references:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    # Apply replacements in reverse order to preserve positions
    result = template_content
    for match, resolved in reversed(resolutions):
        result = result[: match.start()] + resolved + result[match.end() :]

    return result


def compute_output_path(input_path: Path) -> Path:
    """Compute the output path based on naming convention.

    foo.textplate.md → foo.md
    other.md → other.filled.md
    """
    name = input_path.name
    if name.endswith(".textplate.md"):
        out_name = name[: -len(".textplate.md")] + ".md"
    else:
        stem = input_path.stem
        out_name = stem + ".filled.md"
    return input_path.parent / out_name


def make_header(source_file: str) -> str:
    """Generate the header comment for output files."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"<!-- Generated by textplate from {source_file} on {timestamp}. Do not edit directly. -->\n\n"


def press_file(file: Path, *, to_stdout: bool = False) -> str | None:
    """Run the press operation on a single file.

    Returns the output path string on success, or raises ResolveError on failure.
    If to_stdout, writes to stdout and returns None.
    """
    template_content = file.read_text()
    base_dir = file.resolve().parent

    result = process_template(template_content, base_dir)

    header = make_header(file.name)
    output = header + result

    # Ensure trailing newline
    if not output.endswith("\n"):
        output += "\n"

    if to_stdout:
        sys.stdout.write(output)
        return None
    else:
        out_path = compute_output_path(file.resolve())
        out_path.write_text(output)
        return str(out_path)
