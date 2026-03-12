"""Tests for the Markdown parser."""

from pathlib import Path

from markdownpeek.parser import (
    find_section,
    get_section_lines,
    parse_markdown,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _parse_fixture(name: str):
    return parse_markdown((FIXTURES / name).read_text())


class TestHeadingExtraction:
    def test_basic_headings(self):
        parsed = _parse_fixture("basic.md")
        texts = [h.text for h in parsed.headings]
        assert texts == [
            "Title",
            "Section One",
            "Section Two",
            "Subsection",
            "Section Three",
        ]

    def test_heading_levels(self):
        parsed = _parse_fixture("basic.md")
        levels = [h.level for h in parsed.headings]
        assert levels == [1, 2, 2, 3, 2]

    def test_heading_line_numbers(self):
        parsed = _parse_fixture("basic.md")
        line_nums = [h.line_num for h in parsed.headings]
        assert line_nums == [1, 5, 11, 15, 19]

    def test_nested_headings(self):
        parsed = _parse_fixture("nested.md")
        assert len(parsed.headings) == 8
        assert parsed.headings[0].text == "Top Level"
        assert parsed.headings[-1].text == "Section 2.2"

    def test_no_headings(self):
        parsed = _parse_fixture("no_headings.md")
        assert parsed.headings == []

    def test_empty_file(self):
        parsed = parse_markdown("")
        assert parsed.headings == []
        assert parsed.links == []


class TestCodeBlockSkipping:
    def test_headings_in_code_blocks_ignored(self):
        parsed = _parse_fixture("code_blocks.md")
        texts = [h.text for h in parsed.headings]
        # Should NOT include "# not a heading" etc from inside code blocks
        assert "not a heading" not in " ".join(texts).lower()
        assert "Code Examples" in texts
        assert "Python" in texts
        assert "Shell" in texts
        assert "Nested Fences" in texts
        assert "After Code" in texts

    def test_code_blocks_detected(self):
        parsed = _parse_fixture("code_blocks.md")
        assert len(parsed.code_blocks) == 3
        assert parsed.code_blocks[0].language == "python"
        assert parsed.code_blocks[1].language == "bash"
        assert parsed.code_blocks[2].language == "markdown"

    def test_nested_fences(self):
        parsed = _parse_fixture("code_blocks.md")
        # The ```` fence should contain the ``` inside
        nested = parsed.code_blocks[2]
        assert nested.language == "markdown"


class TestFrontMatter:
    def test_front_matter_detected(self):
        parsed = _parse_fixture("frontmatter.md")
        assert parsed.front_matter is not None
        assert parsed.front_matter.line_start == 1
        assert parsed.front_matter.line_end == 5

    def test_headings_after_front_matter(self):
        parsed = _parse_fixture("frontmatter.md")
        assert len(parsed.headings) == 2
        assert parsed.headings[0].text == "Document Title"

    def test_no_front_matter(self):
        parsed = _parse_fixture("basic.md")
        assert parsed.front_matter is None


class TestLinks:
    def test_links_extracted(self):
        parsed = _parse_fixture("links.md")
        non_image = [l for l in parsed.links if not l.is_image]
        assert len(non_image) == 4

    def test_images_extracted(self):
        parsed = _parse_fixture("links.md")
        images = [l for l in parsed.links if l.is_image]
        assert len(images) == 3

    def test_link_properties(self):
        parsed = _parse_fixture("links.md")
        google = next(l for l in parsed.links if l.text == "Google")
        assert google.url == "https://google.com"
        assert not google.is_image

    def test_image_properties(self):
        parsed = _parse_fixture("links.md")
        img = next(l for l in parsed.links if l.text == "Alt text")
        assert img.url == "https://example.com/image.png"
        assert img.is_image


class TestContentEnd:
    def test_section_content_end(self):
        parsed = _parse_fixture("basic.md")
        # "Section One" starts at line 5, "Section Two" at line 11
        sec_one = parsed.headings[1]
        assert sec_one.content_end == 10  # line before Section Two

    def test_last_section_extends_to_end(self):
        parsed = _parse_fixture("basic.md")
        last = parsed.headings[-1]
        assert last.content_end == len(parsed.lines)


class TestFindSection:
    def test_exact_match(self):
        parsed = _parse_fixture("basic.md")
        h = find_section(parsed, "Section One")
        assert h is not None
        assert h.text == "Section One"

    def test_case_insensitive(self):
        parsed = _parse_fixture("basic.md")
        h = find_section(parsed, "section one")
        assert h is not None
        assert h.text == "Section One"

    def test_substring_match(self):
        parsed = _parse_fixture("basic.md")
        h = find_section(parsed, "One")
        assert h is not None
        assert h.text == "Section One"

    def test_no_match(self):
        parsed = _parse_fixture("basic.md")
        assert find_section(parsed, "nonexistent") is None

    def test_first_match_wins(self):
        parsed = _parse_fixture("basic.md")
        h = find_section(parsed, "Section")
        assert h is not None
        assert h.text == "Section One"  # first match


class TestGetSectionLines:
    def test_section_lines(self):
        parsed = _parse_fixture("basic.md")
        h = find_section(parsed, "Section One")
        lines = get_section_lines(parsed, h)
        assert lines[0] == "## Section One"
        assert "Content of section one." in lines

    def test_last_section(self):
        parsed = _parse_fixture("basic.md")
        h = find_section(parsed, "Section Three")
        lines = get_section_lines(parsed, h)
        assert lines[0] == "## Section Three"
        assert "Final section." in lines


class TestEdgeCases:
    def test_windows_line_endings(self):
        text = "# Title\r\n\r\nContent\r\n\r\n## Section\r\n\r\nMore.\r\n"
        parsed = parse_markdown(text)
        assert len(parsed.headings) == 2
        assert parsed.headings[0].text == "Title"

    def test_no_trailing_newline(self):
        text = "# Title\n\nContent"
        parsed = parse_markdown(text)
        assert len(parsed.headings) == 1
        assert len(parsed.lines) == 3

    def test_heading_with_closing_hashes(self):
        text = "## Hello World ##\n"
        parsed = parse_markdown(text)
        assert parsed.headings[0].text == "Hello World"
