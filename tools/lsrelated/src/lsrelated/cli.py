"""CLI entry point for lsrelated."""

from __future__ import annotations

from collections import Counter
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ccdata import ClaudeCodeData
from lsrelated.graph import (
    build_undirected_graph,
    find_file,
    find_display_prefix,
    strip_prefix,
)

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console(force_terminal=True)


TOOL_DESCRIPTION = """\
lsrelated — Find files frequently accessed together in Claude Code sessions.

Builds an undirected co-access graph from Claude Code session data. When two
files are Read/Write/Edited in the same turn, they get an edge. Edge weight
equals the number of turns where both files appear.

COMMANDS

  lsrelated related <file>       Show top related files for a given file
  lsrelated related <file> -n 20 Show more results
  lsrelated related <file> -m    Show all matching files for ambiguous queries
  lsrelated top                  Show files with the most connections
  lsrelated top -n 30            Show more files
  lsrelated tool-description     Print this description

OPTIONS (shared across commands)

  -p, --project TEXT    Filter to a project (case-insensitive substring match)
  --no-subagents        Exclude subagent tool calls from the graph

TYPICAL WORKFLOW

  1. Find what files are related to a file you're working on:
       lsrelated related src/lib/types.ts

  2. Use partial names — suffix and substring matching is supported:
       lsrelated related types.ts

  3. See the most-connected files in a project:
       lsrelated top -p myproject

  4. Compare with and without subagent data:
       lsrelated related types.ts
       lsrelated related types.ts --no-subagents

HOW IT WORKS

  Parses Claude Code session JSONL files from ~/.claude/projects/.
  When two files are Read/Write/Edited in the same turn, they get
  a co-access edge. Files with more edges are more related.
  Subagent tool calls are merged into parent turns by default.

FILE MATCHING

  The <file> argument is resolved in this order:
    1. Exact match against known file paths
    2. Suffix match (e.g. "types.ts" matches "/foo/bar/types.ts")
    3. Substring match
  If multiple files match, the most-accessed one is used.
  Use -m to see all matching files.
"""

TOOL_DESCRIPTION_SHORT = """\
lsrelated — Find files frequently accessed together in Claude Code sessions.

Commands:
  lsrelated related <file>    Top related files (supports partial match)
  lsrelated top               Most-connected files across sessions
  lsrelated tool-description  Full usage docs

Options: -n/--top N, -p/--project TEXT, --no-subagents
"""


@app.command("tool-description")
def tool_description():
    """Print full agent-oriented tool description."""
    print(TOOL_DESCRIPTION)


@app.command("tool-description-short")
def tool_description_short():
    """Print concise tool description suitable for CLAUDE.md."""
    print(TOOL_DESCRIPTION_SHORT)


@app.command()
def related(
    file: str = typer.Argument(help="File path or name to look up (supports partial match)"),
    n: int = typer.Option(10, "-n", "--top", help="Number of related files to show"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Filter to project (substring match)"),
    no_subagents: bool = typer.Option(False, "--no-subagents", help="Exclude subagent tool calls"),
    show_matches: bool = typer.Option(False, "--show-matches", "-m", help="Show all matching files for ambiguous queries"),
    claude_dir: Optional[str] = typer.Option(None, "--claude-dir", help="Path to .claude directory (default: ~/.claude)", hidden=True),
):
    """Find files most frequently accessed alongside a given file."""
    merge = not no_subagents
    cc = ClaudeCodeData(project=project, merge_subagents=merge, claude_dir=claude_dir)
    if cc.session_count == 0:
        console.print("[red]No sessions found.[/red]")
        raise typer.Exit(1)

    sessions = cc.sessions()
    edges, node_counts = build_undirected_graph(sessions)

    # Find the file
    match = find_file(file, node_counts)

    # Find common prefix for display
    prefix = find_display_prefix(list(node_counts.keys()))

    if not match:
        console.print(f"[red]No file matching '{file}' found in session data.[/red]")
        candidates = [f for f in node_counts if file.lower() in f.lower()]
        if candidates:
            candidates.sort(key=lambda f: -node_counts[f])
            console.print("\n[dim]Did you mean:[/dim]")
            for c in candidates[:10]:
                console.print(f"  [cyan]{strip_prefix(c, prefix)}[/cyan]  ({node_counts[c]} accesses)")
        raise typer.Exit(1)

    if show_matches:
        all_matches = [f for f in node_counts if file in f]
        if len(all_matches) > 1:
            console.print(f"[dim]All matches for '{file}':[/dim]")
            for m in sorted(all_matches, key=lambda f: -node_counts[f]):
                marker = " [green]<-[/green]" if m == match else ""
                console.print(f"  [cyan]{strip_prefix(m, prefix)}[/cyan]  ({node_counts[m]} accesses){marker}")
            console.print()

    # Gather related files
    related_files: list[tuple[str, int]] = []
    for (a, b), weight in edges.items():
        if a == match:
            related_files.append((b, weight))
        elif b == match:
            related_files.append((a, weight))

    related_files.sort(key=lambda x: -x[1])
    related_files = related_files[:n]

    if not related_files:
        console.print(f"[yellow]No co-access data for {strip_prefix(match, prefix)}[/yellow]")
        raise typer.Exit(0)

    # Display
    display_path = strip_prefix(match, prefix)
    console.print(f"\n[bold]{display_path}[/bold]  [dim]({node_counts[match]} total accesses)[/dim]\n")

    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("Weight", justify="right", style="cyan", width=8)
    table.add_column("Related File", style="white")

    for path, weight in related_files:
        table.add_row(str(weight), strip_prefix(path, prefix))

    console.print(table)
    console.print()


@app.command()
def top(
    n: int = typer.Option(20, "-n", "--top", help="Number of files to show"),
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Filter to project (substring match)"),
    no_subagents: bool = typer.Option(False, "--no-subagents", help="Exclude subagent tool calls"),
    claude_dir: Optional[str] = typer.Option(None, "--claude-dir", help="Path to .claude directory (default: ~/.claude)", hidden=True),
):
    """Show files with the most co-access connections."""
    merge = not no_subagents
    cc = ClaudeCodeData(project=project, merge_subagents=merge, claude_dir=claude_dir)
    sessions = cc.sessions()
    edges, node_counts = build_undirected_graph(sessions)

    # Rank by total edge weight
    total_weight: Counter[str] = Counter()
    neighbor_count: Counter[str] = Counter()
    for (a, b), w in edges.items():
        total_weight[a] += w
        total_weight[b] += w
        neighbor_count[a] += 1
        neighbor_count[b] += 1

    prefix = find_display_prefix(list(node_counts.keys()))

    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("Weight", justify="right", style="cyan", width=8)
    table.add_column("Neighbors", justify="right", style="dim", width=10)
    table.add_column("File", style="white")

    for path, w in total_weight.most_common(n):
        table.add_row(str(w), str(neighbor_count[path]), strip_prefix(path, prefix))

    console.print()
    console.print(table)
    console.print()


def main():
    app()
