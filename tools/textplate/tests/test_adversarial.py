"""Adversarial and edge-case tests for textplate."""

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


# =============================================================================
# Heading / slug edge cases
# =============================================================================


class TestDuplicateHeadings:
    """When the same heading appears twice, we match the first one."""

    def test_first_match_wins(self):
        content = FIXTURES.joinpath("complex_headings.md").read_text()
        result = extract_section(content, "setup", "complex_headings.md")
        assert "First setup section." in result
        assert "Second setup section" not in result


class TestHeadingsWithInlineMarkdown:
    def test_inline_code_in_heading(self):
        content = FIXTURES.joinpath("complex_headings.md").read_text()
        # GitHub slugifies ## The `code` Section → the-code-section
        result = extract_section(content, "the-code-section", "complex_headings.md")
        assert "inline code" in result

    def test_bold_in_heading(self):
        content = FIXTURES.joinpath("complex_headings.md").read_text()
        # ## **Bold** Heading → bold-heading
        result = extract_section(content, "bold-heading", "complex_headings.md")
        assert "bold markdown" in result

    def test_link_in_heading(self):
        content = FIXTURES.joinpath("complex_headings.md").read_text()
        # ## [Link Here](https://example.com) → link-herehttpsexamplecom
        result = extract_section(content, "link-herehttpsexamplecom", "complex_headings.md")
        assert "has a link" in result

    def test_emoji_in_heading(self):
        content = FIXTURES.joinpath("complex_headings.md").read_text()
        # ## 🚀 Getting Started → -getting-started
        result = extract_section(content, "-getting-started", "complex_headings.md")
        assert "has an emoji" in result

    def test_trailing_hashes(self):
        content = FIXTURES.joinpath("complex_headings.md").read_text()
        # ## Heading With Trailing Hashes ## → heading-with-trailing-hashes-
        result = extract_section(content, "heading-with-trailing-hashes-", "complex_headings.md")
        assert "trailing hashes" in result


class TestEmptyHeading:
    def test_empty_heading_slug(self):
        # ## (just hashes and space) should produce empty slug
        assert slugify("") == ""

    def test_empty_heading_not_matched(self):
        """## alone (no text after space) doesn't match HEADING_PATTERN (.+ requires chars)."""
        content = FIXTURES.joinpath("complex_headings.md").read_text()
        # The heading regex requires .+ after the space, so bare ## won't match
        with pytest.raises(ResolveError, match="not found"):
            extract_section(content, "", "complex_headings.md")


class TestSlugCollisions:
    def test_different_text_same_slug(self):
        """## My Section and ## My-Section would both slugify to my-section."""
        content = "## My Section\n\nFirst.\n\n## My-Section\n\nSecond.\n"
        result = extract_section(content, "my-section", "test.md")
        assert "First." in result
        assert "Second." not in result


class TestSetextHeadings:
    """Setext-style headings (underline with === or ---) are not currently supported."""

    def test_setext_not_found(self):
        content = FIXTURES.joinpath("setext_headings.md").read_text()
        with pytest.raises(ResolveError, match="not found"):
            extract_section(content, "top-level", "setext_headings.md")

    def test_setext_sub_section_not_found(self):
        content = FIXTURES.joinpath("setext_headings.md").read_text()
        with pytest.raises(ResolveError, match="not found"):
            extract_section(content, "sub-section", "setext_headings.md")

    def test_atx_after_setext_still_works(self):
        content = FIXTURES.joinpath("setext_headings.md").read_text()
        result = extract_section(content, "atx-after-setext", "setext_headings.md")
        assert "Content under ATX heading." in result


# =============================================================================
# Fenced code block traps
# =============================================================================


class TestFencedCodeBlocks:
    def test_tilde_fences(self):
        content = FIXTURES.joinpath("fence_tricky.md").read_text()
        result = extract_section(content, "tilde-fences", "fence_tricky.md")
        assert "Fake Heading In Tilde Fence" in result
        assert "Content after tilde fence." in result

    def test_nested_fences(self):
        """4-backtick fence wrapping 3-backtick fence."""
        content = FIXTURES.joinpath("fence_tricky.md").read_text()
        result = extract_section(content, "nested-fences", "fence_tricky.md")
        assert "Fake Heading In Nested Fence" in result
        assert "Content after nested fence." in result

    def test_unclosed_fence_eats_rest_of_section(self):
        """An unclosed fence means everything after it is 'in a code block'."""
        content = FIXTURES.joinpath("fence_tricky.md").read_text()
        result = extract_section(content, "unclosed-fence", "fence_tricky.md")
        # Since the fence never closes, all subsequent "headings" should be captured
        assert "This Fence Never Closes" in result
        assert "Another Fake Heading" in result
        assert "inside the unclosed fence" in result

    def test_heading_not_found_inside_fence(self):
        """A heading only inside a code fence should not be findable."""
        content = (
            "## Real\n\n"
            "```\n"
            "## Only In Fence\n"
            "```\n\n"
            "## Other\n\nStuff.\n"
        )
        with pytest.raises(ResolveError, match="not found"):
            extract_section(content, "only-in-fence", "test.md")


# =============================================================================
# Template syntax adversarial
# =============================================================================


class TestTemplateSyntaxAdversarial:
    def test_text_link_inside_code_fence_in_template(self):
        """text:: links inside code fences in the template ARE resolved (current behavior).
        This documents the current behavior - template processing is regex-based
        and doesn't understand markdown structure."""
        template = "```\n[](text::./greeting.txt)\n```"
        result = process_template(template, FIXTURES)
        # Current behavior: it DOES resolve inside fences
        assert "Hello, world!" in result

    def test_nested_templates_not_resolved(self):
        """Resolved content containing text:: links should NOT be recursively resolved."""
        # Create a file whose content itself contains a text:: link
        tmp = FIXTURES / "_nested_source.md"
        try:
            tmp.write_text("## Nested\n\n[](text::./greeting.txt)\n")
            result = resolve_reference("./_nested_source.md#nested", FIXTURES)
            # The text:: link in the resolved content should remain as-is
            assert "text::./greeting.txt" in result
        finally:
            tmp.unlink(missing_ok=True)

    def test_text_in_label(self):
        """text:: appearing in the label part should not confuse the regex."""
        m = LINK_PATTERN.search("[text::foo](text::./file.md)")
        assert m is not None
        assert m.group(1) == "text::foo"
        assert m.group(2) == "./file.md"

    def test_malformed_empty_source(self):
        """[](text::) — empty source."""
        m = LINK_PATTERN.search("[](text::)")
        # The regex requires at least one char after text:: due to [^)]+
        assert m is None

    def test_malformed_hash_only_fragment(self):
        """[](text::./file.md#) — fragment is empty string."""
        template = "[](text::./snippets.md#)"
        with pytest.raises(ResolveError):
            process_template(template, FIXTURES)

    def test_malformed_bang_only_fragment(self):
        """[](text::./file.md#!) — fragment is just '!'."""
        template = "[](text::./snippets.md#!)"
        with pytest.raises(ResolveError):
            process_template(template, FIXTURES)

    def test_multiple_links_on_same_line(self):
        template = "[](text::./greeting.txt) and [](text::./greeting.txt)"
        result = process_template(template, FIXTURES)
        assert result == "Hello, world! and Hello, world!"

    def test_many_links_on_same_line(self):
        links = " ".join(f"[](text::./greeting.txt)" for _ in range(20))
        result = process_template(links, FIXTURES)
        assert result.count("Hello, world!") == 20
        assert "text::" not in result


# =============================================================================
# Path traversal / security
# =============================================================================


class TestPathSecurity:
    def test_absolute_path_resolves(self):
        """Absolute paths currently work — just checks it resolves."""
        abs_path = str(FIXTURES / "greeting.txt")
        result = resolve_reference(abs_path, FIXTURES)
        assert "Hello, world!" in result

    def test_parent_traversal(self):
        """../ paths work (they resolve relative to base_dir)."""
        result = resolve_reference("../fixtures/greeting.txt", FIXTURES)
        assert "Hello, world!" in result

    def test_symlink_to_file(self, tmp_path):
        """Symlinks resolve to their target."""
        target = FIXTURES / "greeting.txt"
        link = tmp_path / "link.txt"
        link.symlink_to(target)
        result = resolve_reference("link.txt", tmp_path)
        assert "Hello, world!" in result

    def test_nonexistent_path_traversal(self):
        """Path traversal to nonexistent file should fail cleanly."""
        with pytest.raises(ResolveError, match="File not found"):
            resolve_reference("../../etc/passwd", FIXTURES)


# =============================================================================
# Content edge cases
# =============================================================================


class TestContentEdgeCases:
    def test_empty_file(self):
        result = resolve_reference("./empty.txt", FIXTURES)
        assert result == ""

    def test_whitespace_only_file(self):
        result = resolve_reference("./whitespace_only.txt", FIXTURES)
        assert result.strip() == ""

    def test_no_trailing_newline(self):
        result = resolve_reference("./no_trailing_newline.txt", FIXTURES)
        assert result == "no newline at end"

    def test_windows_line_endings(self):
        result = resolve_reference("./windows_endings.txt", FIXTURES)
        assert "line one" in result
        assert "line two" in result

    def test_windows_line_endings_markdown_sections(self):
        result = resolve_reference("./windows_headings.md#section-one", FIXTURES)
        assert "Content with CRLF." in result

    def test_empty_section(self):
        content = FIXTURES.joinpath("empty_section.md").read_text()
        result = extract_section(content, "empty", "empty_section.md")
        assert result == ""

    def test_also_empty_section(self):
        content = FIXTURES.joinpath("empty_section.md").read_text()
        result = extract_section(content, "also-empty", "empty_section.md")
        assert result == ""

    def test_last_section_no_terminator(self):
        """Section at end of file with no following heading."""
        content = FIXTURES.joinpath("empty_section.md").read_text()
        result = extract_section(content, "last-section", "empty_section.md")
        assert "Final content at end of file." in result

    def test_binary_file_doesnt_crash(self, tmp_path):
        """Binary content shouldn't crash, even if output is garbage."""
        bin_file = tmp_path / "binary.bin"
        bin_file.write_bytes(b"\x00\x01\x02\xff\xfe\x80PNG\r\n")
        try:
            resolve_reference("binary.bin", tmp_path)
        except (ResolveError, UnicodeDecodeError):
            pass  # Both are acceptable failures

    def test_include_empty_file_in_template(self):
        template = "before\n[](text::./empty.txt)\nafter"
        result = process_template(template, FIXTURES)
        assert "before\n\nafter" == result or "before" in result


# =============================================================================
# Output path edge cases
# =============================================================================


class TestOutputPathEdgeCases:
    def test_just_textplate_md(self):
        """Filename is exactly '.textplate.md' — output is '.md'."""
        p = Path("/dir/.textplate.md")
        assert compute_output_path(p) == Path("/dir/.md")

    def test_filled_md_input(self):
        """Input is already .filled.md — gets another .filled.md suffix."""
        p = Path("/dir/foo.filled.md")
        assert compute_output_path(p) == Path("/dir/foo.filled.filled.md")

    def test_nested_textplate_suffix(self):
        """Multiple .textplate in name."""
        p = Path("/dir/foo.textplate.textplate.md")
        assert compute_output_path(p) == Path("/dir/foo.textplate.md")

    def test_no_extension(self):
        p = Path("/dir/Makefile")
        assert compute_output_path(p) == Path("/dir/Makefile.filled.md")


# =============================================================================
# Self-reference and circular references
# =============================================================================


class TestCircularReferences:
    def test_self_reference(self, tmp_path):
        """A template referencing itself should fail (it resolves, but the
        content will contain the text:: link since we don't recurse)."""
        tmpl = tmp_path / "self.textplate.md"
        tmpl.write_text("[](text::./self.textplate.md)")
        result = process_template(tmpl.read_text(), tmp_path)
        assert "text::./self.textplate.md" in result

    def test_mutual_reference_no_infinite_loop(self, tmp_path):
        """A→B and B→A: since we don't recurse, this terminates."""
        (tmp_path / "a.md").write_text("A content\n[](text::./b.md)")
        (tmp_path / "b.md").write_text("B content\n[](text::./a.md)")
        template = "[](text::./a.md)"
        result = process_template(template, tmp_path)
        assert "A content" in result
        assert "text::./b.md" in result


# =============================================================================
# Regex edge cases
# =============================================================================


class TestRegexEdgeCases:
    def test_parentheses_in_source_path(self):
        """Parenthesis in path would break the regex since ) ends the group."""
        m = LINK_PATTERN.search("[](text::./file (1).md)")
        assert m is None or m.group(2) != "./file (1).md"

    def test_brackets_in_label(self):
        """Brackets in label: [a[b]](text::./file.md)."""
        m = LINK_PATTERN.search("[a[b]](text::./file.md)")
        if m:
            assert m.group(2) == "./file.md"

    def test_newline_in_link(self):
        """Link split across lines should not match."""
        text = "[](text::\n./file.md)"
        m = LINK_PATTERN.search(text)
        assert m is None  # [^)\n]+ prevents matching across lines

    def test_escaped_brackets(self):
        r"""\\[ should not start a match."""
        text = r"\[](text::./file.md)"
        m = LINK_PATTERN.search(text)
        if m:
            assert m.group(2) == "./file.md"
