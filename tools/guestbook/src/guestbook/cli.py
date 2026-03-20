"""CLI entry point for guestbook."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from guestbook.storage import find_marker, read_entries, write_entry, MARKER_NAME

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console(force_terminal=True)


TOOL_DESCRIPTION = """\
guestbook — Structured entry logging triggered by GUESTBOOK.md marker files.

Place a GUESTBOOK.md file in any directory to create a guestbook. Agents and
users can then sign entries (arbitrary JSON) which are stored in
.guestbook/entries.jsonl next to the marker. Discovery walks up the directory
tree, so subdirectories inherit the nearest guestbook.

COMMANDS

  guestbook init [PATH]            Create a GUESTBOOK.md marker (default: cwd)
  guestbook sign [--dir PATH]      Record an entry (reads JSON from stdin)
  guestbook read [--dir PATH]      Print all entries from the nearest guestbook
  guestbook find [--dir PATH]      Print path to the nearest GUESTBOOK.md
  guestbook tool-description       Print this description
  guestbook tool-description-short Print short description

STORAGE

  GUESTBOOK.md is the marker file (placed by user or `guestbook init`).
  .guestbook/entries.jsonl stores one JSON object per line next to the marker.
  Each entry gets an automatic `timestamp` field (ISO 8601 UTC).

TYPICAL WORKFLOW

  1. Create a guestbook:
       guestbook init /path/to/project

  2. Sign an entry (pipe JSON via stdin):
       echo '{"task": "refactor auth", "agent": "claude"}' | guestbook sign

  3. Read entries:
       guestbook read

  4. Find the nearest guestbook from a subdirectory:
       guestbook find --dir /path/to/project/src/deep/nested
"""

TOOL_DESCRIPTION_SHORT = """\
guestbook — Structured entry logging triggered by GUESTBOOK.md marker files.

Usage:
  guestbook init [PATH]         Create a GUESTBOOK.md marker
  guestbook sign [--dir PATH]   Record a JSON entry from stdin
  guestbook read [--dir PATH]   Print all entries
  guestbook find [--dir PATH]   Find nearest GUESTBOOK.md
"""


def _resolve_marker(dir_path: Optional[Path]) -> Path:
    """Find the nearest marker or exit with an error."""
    start = Path(dir_path) if dir_path else Path.cwd()
    marker = find_marker(start)
    if marker is None:
        console.print(
            f"[red]No GUESTBOOK.md found at or above {start}[/red]",
            file=sys.stderr,
        )
        raise typer.Exit(1)
    return marker


@app.command()
def init(path: Optional[Path] = typer.Argument(None, help="Directory to create GUESTBOOK.md in (default: cwd)")) -> None:
    """Create a GUESTBOOK.md marker file."""
    target = Path(path) if path else Path.cwd()
    target.mkdir(parents=True, exist_ok=True)
    marker = target / MARKER_NAME
    if marker.exists():
        console.print(f"GUESTBOOK.md already exists at {marker}")
        return
    marker.touch()
    console.print(f"Created {marker}")


@app.command()
def sign(dir: Optional[Path] = typer.Option(None, "--dir", help="Start directory for marker search")) -> None:
    """Record an entry. Reads JSON from stdin."""
    marker = _resolve_marker(dir)

    raw = sys.stdin.read().strip()
    if not raw:
        console.print("[red]No input on stdin. Pipe JSON to sign.[/red]", file=sys.stderr)
        raise typer.Exit(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        console.print(f"[red]Invalid JSON on stdin: {e}[/red]", file=sys.stderr)
        raise typer.Exit(1)

    if not isinstance(data, dict):
        console.print("[red]Stdin JSON must be an object, not an array or scalar.[/red]", file=sys.stderr)
        raise typer.Exit(1)

    write_entry(marker, data)
    console.print(f"Signed guestbook at {marker.parent}")


@app.command()
def read(dir: Optional[Path] = typer.Option(None, "--dir", help="Start directory for marker search")) -> None:
    """Read entries from the nearest guestbook."""
    marker = _resolve_marker(dir)
    entries = read_entries(marker)

    if not entries:
        console.print("No entries yet.")
        return

    for entry in entries:
        ts = entry.pop("timestamp", "?")
        fields = "  ".join(f"{k}={v}" for k, v in entry.items())
        console.print(f"[dim]{ts}[/dim]  {fields}")


@app.command()
def find(dir: Optional[Path] = typer.Option(None, "--dir", help="Start directory for marker search")) -> None:
    """Find the nearest GUESTBOOK.md marker."""
    start = Path(dir) if dir else Path.cwd()
    marker = find_marker(start)
    if marker is None:
        console.print(f"No GUESTBOOK.md found at or above {start}", file=sys.stderr)
        raise typer.Exit(1)
    # Print raw path (no rich markup) for machine consumption
    print(str(marker))


@app.command("tool-description")
def tool_description() -> None:
    """Print full tool description."""
    print(TOOL_DESCRIPTION)


@app.command("tool-description-short")
def tool_description_short() -> None:
    """Print short tool description."""
    print(TOOL_DESCRIPTION_SHORT)


def main() -> None:
    app()
