"""Tests for markdownpeek CLI meta commands and error handling."""

from markdownpeek.cli import main


def test_tool_description_exits_zero():
    assert main(["tool-description"]) == 0


def test_tool_description_short_exits_zero():
    assert main(["tool-description-short"]) == 0


def test_tool_description_has_content(capsys):
    main(["tool-description"])
    out = capsys.readouterr().out
    assert "markdownpeek" in out
    assert "toc" in out


def test_tool_description_short_has_content(capsys):
    main(["tool-description-short"])
    out = capsys.readouterr().out
    assert "markdownpeek" in out
    assert "SETUP" in out


def test_help_exits_zero():
    assert main(["help"]) == 0


def test_help_subcommand(capsys):
    assert main(["help", "toc"]) == 0
    out = capsys.readouterr().out
    assert "toc" in out


def test_help_unknown_command(capsys):
    assert main(["help", "nonexistent"]) == 1


def test_unknown_command_exits_nonzero():
    assert main(["nonexistent"]) != 0


def test_no_args_shows_help(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "markdownpeek" in out
