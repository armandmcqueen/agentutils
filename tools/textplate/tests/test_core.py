"""Tests for textplate core logic."""

from pathlib import Path

import pytest

from textplate.core import (
    LINK_PATTERN,
    ResolveError,
    compute_output_path,
    extract_section,
    process_template,
    resolve_reference,
    slugify,
)

FIXTURES = Path(__file__).parent / "fixtures"


# --- Regex ---


class TestLinkPattern:
    def test_matches_empty_label(self):
        m = LINK_PATTERN.search("[](text::./file.md)")
        assert m is not None
        assert m.group(1) == ""
        assert m.group(2) == "./file.md"

    def test_matches_with_label(self):
        m = LINK_PATTERN.search("[fallback](text::./file.md#section)")
        assert m is not None
        assert m.group(1) == "fallback"
        assert m.group(2) == "./file.md#section"

    def test_no_match_for_normal_links(self):
        assert LINK_PATTERN.search("[label](https://example.com)") is None

    def test_multiple_matches(self):
        text = "[](text::a.md) and [](text::b.md)"
        matches = LINK_PATTERN.findall(text)
        assert len(matches) == 2


# --- Slugify ---


class TestSlugify:
    def test_basic(self):
        assert slugify("Intro") == "intro"

    def test_spaces_to_hyphens(self):
        assert slugify("My Section") == "my-section"

    def test_strips_punctuation(self):
        assert slugify("What's New?") == "whats-new"

    def test_multiple_spaces(self):
        assert slugify("A   B") == "a-b"

    def test_already_slug(self):
        assert slugify("already-a-slug") == "already-a-slug"


# --- Section extraction ---


class TestExtractSection:
    def test_extracts_section_by_heading(self):
        content = FIXTURES.joinpath("snippets.md").read_text()
        result = extract_section(content, "intro", "snippets.md")
        assert "**intro** section" in result
        assert "multiple lines" in result

    def test_extracts_second_section(self):
        content = FIXTURES.joinpath("snippets.md").read_text()
        result = extract_section(content, "usage", "snippets.md")
        assert "textplate press" in result

    def test_section_includes_sub_headings(self):
        """A ## section should include ### sub-headings within it."""
        content = FIXTURES.joinpath("snippets.md").read_text()
        result = extract_section(content, "usage", "snippets.md")
        assert "Advanced Usage" in result
        assert "--stdout" in result

    def test_section_stops_at_same_level(self):
        """A ## section stops at the next ## heading."""
        content = FIXTURES.joinpath("snippets.md").read_text()
        result = extract_section(content, "intro", "snippets.md")
        assert "textplate press" not in result  # belongs to ## Usage

    def test_missing_section_raises(self):
        content = FIXTURES.joinpath("snippets.md").read_text()
        with pytest.raises(ResolveError, match="not found"):
            extract_section(content, "nonexistent", "snippets.md")

    def test_top_level_heading(self):
        """Can extract a top-level # heading section."""
        content = "# Top\n\nSome content.\n\n# Other\n\nOther content.\n"
        result = extract_section(content, "top", "test.md")
        assert "Some content." in result
        assert "Other content." not in result

    def test_exclude_heading_by_default(self):
        content = "## Intro\n\nBody text.\n"
        result = extract_section(content, "intro", "test.md")
        assert "## Intro" not in result
        assert "Body text." in result

    def test_include_heading(self):
        content = "## Intro\n\nBody text.\n"
        result = extract_section(content, "intro", "test.md", include_heading=True)
        assert result.startswith("## Intro")
        assert "Body text." in result

    def test_ignores_headings_in_fenced_code_blocks(self):
        """Headings inside ``` code blocks should not end a section."""
        content = (
            "## Examples\n\n"
            "Here is an example:\n\n"
            "```markdown\n"
            "## This Is Not A Real Heading\n"
            "```\n\n"
            "More content after the code block.\n\n"
            "## Next Section\n\n"
            "Different stuff.\n"
        )
        result = extract_section(content, "examples", "test.md")
        assert "This Is Not A Real Heading" in result
        assert "More content after the code block." in result
        assert "Different stuff." not in result


# --- Reference resolution ---


class TestResolveReference:
    def test_whole_file(self):
        result = resolve_reference("./greeting.txt", FIXTURES)
        assert result == "Hello, world!"

    def test_file_with_section(self):
        result = resolve_reference("./snippets.md#intro", FIXTURES)
        assert "**intro** section" in result

    def test_missing_file_raises(self):
        with pytest.raises(ResolveError, match="File not found"):
            resolve_reference("./nonexistent.md", FIXTURES)

    def test_missing_section_raises(self):
        with pytest.raises(ResolveError, match="not found"):
            resolve_reference("./snippets.md#nope", FIXTURES)

    def test_section_excludes_heading_by_default(self):
        result = resolve_reference("./snippets.md#intro", FIXTURES)
        assert "## Intro" not in result
        assert "**intro** section" in result

    def test_section_includes_heading_with_bang(self):
        result = resolve_reference("./snippets.md#intro!", FIXTURES)
        assert "## Intro" in result
        assert "**intro** section" in result


# --- Template processing ---


class TestProcessTemplate:
    def test_simple_template(self):
        template = "Before\n\n[](text::./greeting.txt)\n\nAfter"
        result = process_template(template, FIXTURES)
        assert "Hello, world!" in result
        assert "Before" in result
        assert "After" in result
        assert "text::" not in result

    def test_section_reference(self):
        template = "[](text::./snippets.md#intro)"
        result = process_template(template, FIXTURES)
        assert "**intro** section" in result

    def test_multiple_references(self):
        template = "[](text::./greeting.txt)\n\n[](text::./snippets.md#usage)"
        result = process_template(template, FIXTURES)
        assert "Hello, world!" in result
        assert "textplate press" in result

    def test_no_references_passthrough(self):
        template = "# Just markdown\n\nNo links here."
        result = process_template(template, FIXTURES)
        assert result == template

    def test_strict_mode_all_fail(self):
        template = "[](text::./missing1.md)\n[](text::./missing2.md)"
        with pytest.raises(ResolveError, match="missing1"):
            process_template(template, FIXTURES)


# --- Output path ---


class TestComputeOutputPath:
    def test_textplate_suffix(self):
        p = Path("/some/dir/readme.textplate.md")
        assert compute_output_path(p) == Path("/some/dir/readme.md")

    def test_other_suffix(self):
        p = Path("/some/dir/notes.md")
        assert compute_output_path(p) == Path("/some/dir/notes.filled.md")
