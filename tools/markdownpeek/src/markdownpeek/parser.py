"""Line-based Markdown parser for structural exploration."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Heading:
    level: int
    text: str
    line_num: int  # 1-based
    content_start: int  # 1-based, first line after heading
    content_end: int  # 1-based, last line of section content (inclusive)


@dataclass
class Link:
    text: str
    url: str
    line_num: int  # 1-based
    is_image: bool


@dataclass
class CodeBlock:
    language: str  # empty string if no language specified
    line_start: int  # 1-based, the fence line
    line_end: int  # 1-based, the closing fence line


@dataclass
class FrontMatter:
    line_start: int  # 1-based
    line_end: int  # 1-based


@dataclass
class ParsedMarkdown:
    lines: list[str]
    headings: list[Heading] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    code_blocks: list[CodeBlock] = field(default_factory=list)
    front_matter: FrontMatter | None = None


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+)?\s*$")
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})(.*)?$")
_LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)]*)\)")


def parse_markdown(text: str) -> ParsedMarkdown:
    """Parse markdown text into structural elements.

    Single-pass line scanner that tracks code block and front matter state.
    """
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    # Remove trailing empty line from split if text ends with newline
    if lines and lines[-1] == "" and text.endswith("\n"):
        lines = lines[:-1]

    parsed = ParsedMarkdown(lines=lines)

    in_code_block = False
    code_fence_char = ""
    code_fence_len = 0
    code_block_start = 0
    code_block_lang = ""

    in_front_matter = False
    front_matter_start = 0

    for i, line in enumerate(lines):
        line_num = i + 1  # 1-based

        # Front matter detection: --- at very first line
        if line_num == 1 and line.strip() == "---":
            in_front_matter = True
            front_matter_start = line_num
            continue

        if in_front_matter:
            if line.strip() == "---":
                parsed.front_matter = FrontMatter(
                    line_start=front_matter_start, line_end=line_num
                )
                in_front_matter = False
            continue

        # Code fence detection
        fence_match = _FENCE_RE.match(line.strip())
        if fence_match:
            fence = fence_match.group(1)
            if not in_code_block:
                in_code_block = True
                code_fence_char = fence[0]
                code_fence_len = len(fence)
                code_block_lang = (fence_match.group(2) or "").strip()
                code_block_start = line_num
                continue
            else:
                # Closing fence must use same char and be at least as long
                if fence[0] == code_fence_char and len(fence) >= code_fence_len:
                    parsed.code_blocks.append(
                        CodeBlock(
                            language=code_block_lang,
                            line_start=code_block_start,
                            line_end=line_num,
                        )
                    )
                    in_code_block = False
                continue

        if in_code_block:
            continue

        # Heading detection
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            text_content = heading_match.group(2).strip()
            parsed.headings.append(
                Heading(
                    level=level,
                    text=text_content,
                    line_num=line_num,
                    content_start=line_num + 1,
                    content_end=0,  # filled in second pass
                )
            )

        # Link detection (can appear on any non-code line, including heading lines)
        for link_match in _LINK_RE.finditer(line):
            parsed.links.append(
                Link(
                    text=link_match.group(2),
                    url=link_match.group(3),
                    line_num=line_num,
                    is_image=link_match.group(1) == "!",
                )
            )

    # Handle unclosed code block
    if in_code_block:
        parsed.code_blocks.append(
            CodeBlock(
                language=code_block_lang,
                line_start=code_block_start,
                line_end=len(lines),
            )
        )

    # Second pass: compute content_end for each heading
    # A section extends until the next heading of same or higher level (lower number)
    total_lines = len(lines)
    for i, heading in enumerate(parsed.headings):
        heading.content_end = total_lines  # default: extends to end of file
        for j in range(i + 1, len(parsed.headings)):
            if parsed.headings[j].level <= heading.level:
                heading.content_end = parsed.headings[j].line_num - 1
                break

    return parsed


def find_section(parsed: ParsedMarkdown, query: str) -> Heading | None:
    """Find first heading matching query (case-insensitive substring)."""
    query_lower = query.lower()
    for heading in parsed.headings:
        if query_lower in heading.text.lower():
            return heading
    return None


def get_section_lines(parsed: ParsedMarkdown, heading: Heading) -> list[str]:
    """Get all lines belonging to a section (heading line + content)."""
    start = heading.line_num - 1  # 0-based
    end = heading.content_end  # content_end is 1-based inclusive, so this is correct for slicing
    return parsed.lines[start:end]
