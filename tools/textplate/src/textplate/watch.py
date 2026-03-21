"""Watch loop and progress bar for textplate."""

from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.text import Text

from textplate.core import ResolveError, compute_output_path, press_file

console = Console()

# Interval pattern: number followed by s/m/h/d
INTERVAL_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)\s*([smhd])$", re.IGNORECASE)

INTERVAL_MULTIPLIERS = {"s": 1, "m": 60, "h": 3600, "d": 86400}

BAR_CHAR = "━"
BAR_WIDTH = 40
TICK_INTERVAL = 0.1  # seconds between progress updates


def parse_interval(text: str) -> float:
    """Parse an interval string like '5s', '2m', '1.5h', '1d' into seconds."""
    m = INTERVAL_PATTERN.match(text.strip())
    if not m:
        raise ValueError(
            f"Invalid interval '{text}'. Use format like: 5s, 30s, 2m, 1h, 1d"
        )
    value = float(m.group(1))
    unit = m.group(2).lower()
    return value * INTERVAL_MULTIPLIERS[unit]


def format_interval(seconds: float) -> str:
    """Format seconds into a human-readable interval string."""
    if seconds < 60:
        return f"{seconds:.0f}s" if seconds == int(seconds) else f"{seconds:.1f}s"
    if seconds < 3600:
        m = seconds / 60
        return f"{m:.0f}m" if m == int(m) else f"{m:.1f}m"
    if seconds < 86400:
        h = seconds / 3600
        return f"{h:.0f}h" if h == int(h) else f"{h:.1f}h"
    d = seconds / 86400
    return f"{d:.0f}d" if d == int(d) else f"{d:.1f}d"


def _render_progress_bar(fraction: float, width: int = BAR_WIDTH) -> Text:
    """Render a draining progress bar: filled portion + empty portion.

    fraction: 1.0 = full (just pressed), drains toward 0.0 (about to press).
    """
    filled = int(round(fraction * width))
    filled = max(0, min(width, filled))
    empty = width - filled

    bar = Text()
    bar.append(BAR_CHAR * filled, style="cyan")
    bar.append(BAR_CHAR * empty, style="dim")
    return bar


def watch_file(
    file: Path,
    interval_seconds: float,
    *,
    strict: bool = False,
    verbose: bool = False,
    no_progress: bool = False,
) -> None:
    """Watch a template file and re-press it on a regular interval.

    Receives pre-parsed interval in seconds. Argument validation (file existence,
    interval parsing/minimum) is done by the CLI layer.
    """
    out_path = compute_output_path(file.resolve())
    interval_str = format_interval(interval_seconds)

    console.print(
        f"[cyan]watching[/cyan] {file.name} → {out_path.name}  "
        f"[dim]every {interval_str}[/dim]  [dim]ctrl-c to stop[/dim]",
        highlight=False,
    )

    run_count = 0
    error_count = 0

    try:
        while True:
            # Press the file
            run_count += 1
            try:
                press_file(file)
                if verbose:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    status = Text()
                    status.append(f"  {timestamp} ", style="dim")
                    status.append("pressed", style="green")
                    status.append(f"  #{run_count}", style="dim")
                    console.print(status, highlight=False)
            except (ResolveError, OSError) as e:
                error_count += 1
                timestamp = datetime.now().strftime("%H:%M:%S")
                status = Text()
                status.append(f"  {timestamp} ", style="dim")
                status.append("error", style="red")
                status.append(f"  {e}", style="dim")
                console.print(status, highlight=False)
                if strict:
                    raise typer.Exit(code=1)

            # Wait for next interval
            if no_progress:
                time.sleep(interval_seconds)
            else:
                start = time.monotonic()
                try:
                    while True:
                        elapsed = time.monotonic() - start
                        remaining = interval_seconds - elapsed
                        if remaining <= 0:
                            break
                        fraction = remaining / interval_seconds
                        bar = _render_progress_bar(fraction)

                        line = Text()
                        line.append("  ")
                        line.append_text(bar)
                        remaining_str = format_interval(remaining)
                        line.append(f"  {remaining_str}", style="dim")

                        console.print(line, end="\r", highlight=False)
                        time.sleep(min(TICK_INTERVAL, remaining))

                    # Clear the progress line
                    console.print(" " * (BAR_WIDTH + 20), end="\r")
                except KeyboardInterrupt:
                    # Clear the progress line before re-raising
                    console.print(" " * (BAR_WIDTH + 20), end="\r")
                    raise

    except KeyboardInterrupt:
        console.print()
        summary = Text()
        summary.append("stopped", style="yellow")
        summary.append(f"  {run_count} runs", style="dim")
        if error_count:
            summary.append(f", {error_count} errors", style="red")
        console.print(summary, highlight=False)
