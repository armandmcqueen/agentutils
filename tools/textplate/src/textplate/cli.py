"""CLI entry point for textplate."""

from __future__ import annotations

from pathlib import Path

import typer

from textplate.core import ResolveError, press_file
from textplate.help import COMMAND_HELP, TOOL_DESCRIPTION, TOOL_DESCRIPTION_SHORT
from textplate.watch import parse_interval, watch_file

app = typer.Typer(
    help="Markdown-based templating tool.",
    invoke_without_command=True,
    no_args_is_help=True,
)


@app.callback()
def _callback() -> None:
    """Markdown-based templating tool."""


@app.command("press")
def press(
    file: Path = typer.Argument(..., help="Path to a .textplate.md file to process"),
    stdout: bool = typer.Option(False, "--stdout", help="Print output to stdout instead of writing a file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show output path after pressing"),
) -> None:
    """Resolve all text:: references in a template file and produce plain markdown."""
    if not file.is_file():
        typer.echo(f"Error: File not found: {file}", err=True)
        raise typer.Exit(code=1)

    try:
        out_path = press_file(file, to_stdout=stdout)
    except ResolveError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    if out_path and verbose:
        typer.echo(f"Wrote {out_path}")


@app.command("watch")
def watch(
    file: Path = typer.Argument(..., help="Path to a .textplate.md file to process"),
    every: str = typer.Option("5s", "--every", "-e", help="Interval between runs (e.g. 5s, 30s, 2m, 1h)"),
    strict: bool = typer.Option(False, "--strict", help="Exit on first error instead of continuing"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show status after each press"),
    no_progress: bool = typer.Option(False, "--no-progress", help="Disable the animated progress bar"),
) -> None:
    """Watch a template file and re-press it on a regular interval."""
    from textplate.watch import console

    if not file.is_file():
        console.print(f"[red]Error:[/red] File not found: {file}", highlight=False)
        raise typer.Exit(code=1)

    try:
        interval_seconds = parse_interval(every)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}", highlight=False)
        raise typer.Exit(code=1)

    if interval_seconds < 0.5:
        console.print("[red]Error:[/red] Interval must be at least 0.5s", highlight=False)
        raise typer.Exit(code=1)

    watch_file(file, interval_seconds, strict=strict, verbose=verbose, no_progress=no_progress)


@app.command("tool-description")
def tool_description() -> None:
    """Print full agent-oriented tool description."""
    typer.echo(TOOL_DESCRIPTION)


@app.command("tool-description-short")
def tool_description_short() -> None:
    """Print concise tool description for CLAUDE.md."""
    typer.echo(TOOL_DESCRIPTION_SHORT)


def main() -> None:
    """Entry point for the textplate CLI."""
    app()
