"""Integration tests for all CLI commands."""

from pathlib import Path

from markdownpeek.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def _run(args: list[str], capsys) -> tuple[str, str, int]:
    """Run main() and return (stdout, stderr, exit_code)."""
    code = main(args)
    captured = capsys.readouterr()
    return captured.out, captured.err, code


class TestToc:
    def test_basic(self, capsys):
        out, _, code = _run(["toc", str(FIXTURES / "basic.md")], capsys)
        assert code == 0
        assert "Title" in out
        assert "Section One" in out
        assert "Section Two" in out
        assert "Subsection" in out

    def test_line_numbers(self, capsys):
        out, _, code = _run(["toc", str(FIXTURES / "basic.md")], capsys)
        assert code == 0
        # Title is on line 1
        assert "1:" in out

    def test_indentation(self, capsys):
        out, _, code = _run(["toc", str(FIXTURES / "nested.md")], capsys)
        assert code == 0
        lines = out.strip().split("\n")
        # h1 should have less indent than h2
        h1_line = [l for l in lines if "Top Level" in l][0]
        h2_line = [l for l in lines if "Chapter 1" in l][0]
        # After the colon, h2 should have more leading spaces
        h1_text = h1_line.split(":", 1)[1]
        h2_text = h2_line.split(":", 1)[1]
        assert len(h2_text) - len(h2_text.lstrip()) > len(h1_text) - len(h1_text.lstrip())

    def test_no_headings(self, capsys):
        out, _, code = _run(["toc", str(FIXTURES / "no_headings.md")], capsys)
        assert code == 0
        assert "no headings" in out

    def test_code_block_headings_excluded(self, capsys):
        out, _, code = _run(["toc", str(FIXTURES / "code_blocks.md")], capsys)
        assert code == 0
        assert "not a heading" not in out


class TestPeek:
    def test_whole_file(self, capsys):
        out, _, code = _run(["peek", str(FIXTURES / "basic.md")], capsys)
        assert code == 0
        assert "Title" in out

    def test_section(self, capsys):
        out, _, code = _run(["peek", str(FIXTURES / "basic.md"), "Section One"], capsys)
        assert code == 0
        assert "Section One" in out
        assert "Content of section one" in out

    def test_section_not_found(self, capsys):
        _, err, code = _run(["peek", str(FIXTURES / "basic.md"), "nonexistent"], capsys)
        assert code == 1
        assert "No section" in err

    def test_truncation(self, capsys):
        out, _, code = _run(
            ["peek", str(FIXTURES / "basic.md"), "--lines", "3"], capsys
        )
        assert code == 0
        assert "more lines" in out

    def test_custom_lines(self, capsys):
        out, _, code = _run(
            ["peek", str(FIXTURES / "basic.md"), "--lines", "100"], capsys
        )
        assert code == 0
        assert "more lines" not in out

    def test_case_insensitive_section(self, capsys):
        out, _, code = _run(["peek", str(FIXTURES / "basic.md"), "section one"], capsys)
        assert code == 0
        assert "Section One" in out


class TestGet:
    def test_basic(self, capsys):
        out, _, code = _run(["get", str(FIXTURES / "basic.md"), "Section One"], capsys)
        assert code == 0
        assert "Section One" in out
        assert "Content of section one" in out

    def test_not_found(self, capsys):
        _, err, code = _run(["get", str(FIXTURES / "basic.md"), "nope"], capsys)
        assert code == 1
        assert "No section" in err

    def test_no_line_numbers(self, capsys):
        out, _, code = _run(
            ["get", str(FIXTURES / "basic.md"), "Section One", "--no-line-numbers"],
            capsys,
        )
        assert code == 0
        # Should not have line number prefix pattern
        lines = out.strip().split("\n")
        assert lines[0] == "## Section One"

    def test_with_line_numbers(self, capsys):
        out, _, code = _run(["get", str(FIXTURES / "basic.md"), "Section One"], capsys)
        assert code == 0
        # First line should have a line number
        first_line = out.strip().split("\n")[0]
        assert ":" in first_line
        assert "5" in first_line  # Section One is on line 5

    def test_subsection_included(self, capsys):
        out, _, code = _run(["get", str(FIXTURES / "basic.md"), "Section Two"], capsys)
        assert code == 0
        # Section Two contains the Subsection
        assert "Subsection" in out


class TestStats:
    def test_basic(self, capsys):
        out, _, code = _run(["stats", str(FIXTURES / "basic.md")], capsys)
        assert code == 0
        assert "Lines:" in out
        assert "Words:" in out
        assert "Headings:" in out

    def test_heading_levels(self, capsys):
        out, _, code = _run(["stats", str(FIXTURES / "basic.md")], capsys)
        assert code == 0
        assert "h1:" in out
        assert "h2:" in out
        assert "h3:" in out

    def test_code_blocks(self, capsys):
        out, _, code = _run(["stats", str(FIXTURES / "code_blocks.md")], capsys)
        assert code == 0
        assert "Code blocks:" in out
        assert "python:" in out
        assert "bash:" in out

    def test_links_and_images(self, capsys):
        out, _, code = _run(["stats", str(FIXTURES / "links.md")], capsys)
        assert code == 0
        assert "Links:" in out
        assert "Images:" in out

    def test_front_matter(self, capsys):
        out, _, code = _run(["stats", str(FIXTURES / "frontmatter.md")], capsys)
        assert code == 0
        assert "Front matter:" in out

    def test_largest_section(self, capsys):
        out, _, code = _run(["stats", str(FIXTURES / "basic.md")], capsys)
        assert code == 0
        assert "Largest section:" in out

    def test_empty_file(self, capsys):
        out, _, code = _run(["stats", str(FIXTURES / "empty.md")], capsys)
        assert code == 0
        assert "Lines: 0" in out or "Lines:" in out


class TestLinks:
    def test_all_links(self, capsys):
        out, _, code = _run(["links", str(FIXTURES / "links.md")], capsys)
        assert code == 0
        assert "Google" in out
        assert "GitHub" in out
        assert "Alt text" in out

    def test_images_only(self, capsys):
        out, _, code = _run(
            ["links", str(FIXTURES / "links.md"), "--images-only"], capsys
        )
        assert code == 0
        assert "IMG" in out
        assert "LNK" not in out

    def test_external_only(self, capsys):
        out, _, code = _run(
            ["links", str(FIXTURES / "links.md"), "--external-only"], capsys
        )
        assert code == 0
        assert "google.com" in out
        assert "logo.svg" not in out

    def test_no_links(self, capsys):
        out, _, code = _run(["links", str(FIXTURES / "no_headings.md")], capsys)
        assert code == 0
        assert "no links" in out


class TestSearch:
    def test_literal_search(self, capsys):
        out, _, code = _run(
            ["search", str(FIXTURES / "basic.md"), "Content"], capsys
        )
        assert code == 0
        assert "Content" in out

    def test_no_matches(self, capsys):
        out, _, code = _run(
            ["search", str(FIXTURES / "basic.md"), "zzzzzzz"], capsys
        )
        assert code == 0
        assert "no matches" in out

    def test_case_insensitive(self, capsys):
        out, _, code = _run(
            ["search", str(FIXTURES / "basic.md"), "content"], capsys
        )
        assert code == 0
        assert "Content" in out or "content" in out

    def test_regex_search(self, capsys):
        out, _, code = _run(
            ["search", str(FIXTURES / "basic.md"), "Section \\w+", "--regex"], capsys
        )
        assert code == 0
        assert "Section" in out

    def test_context_lines(self, capsys):
        out, _, code = _run(
            ["search", str(FIXTURES / "basic.md"), "Content of section one", "-C", "1"],
            capsys,
        )
        assert code == 0
        # Should show context lines
        output_lines = out.strip().split("\n")
        # More lines than just the match + section header
        assert len(output_lines) >= 3

    def test_section_grouping(self, capsys):
        out, _, code = _run(
            ["search", str(FIXTURES / "basic.md"), "Content"], capsys
        )
        assert code == 0
        # Should have section headers
        assert "──" in out

    def test_invalid_regex(self, capsys):
        _, err, code = _run(
            ["search", str(FIXTURES / "basic.md"), "[invalid", "--regex"], capsys
        )
        assert code == 1
        assert "Invalid regex" in err
