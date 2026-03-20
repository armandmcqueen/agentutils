"""Guestbook marker discovery and JSONL storage."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

MARKER_NAME = "GUESTBOOK.md"
DATA_DIR = ".guestbook"
ENTRIES_FILE = "entries.jsonl"


def find_marker(start: Path) -> Path | None:
    """Walk up from start to find the nearest GUESTBOOK.md. Returns its path or None."""
    current = start.resolve()
    while True:
        candidate = current / MARKER_NAME
        if candidate.is_file():
            return candidate
        parent = current.parent
        if parent == current:
            return None
        current = parent


def entries_path(marker: Path) -> Path:
    """Return the entries.jsonl path next to a marker file."""
    return marker.parent / DATA_DIR / ENTRIES_FILE


def write_entry(marker: Path, data: dict) -> Path:
    """Write a JSON entry to the guestbook. Adds timestamp automatically.

    Returns the path to the entries file.
    """
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), **data}
    path = entries_path(marker)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    return path


def read_entries(marker: Path) -> list[dict]:
    """Read all entries from a guestbook. Returns empty list if no entries exist."""
    path = entries_path(marker)
    if not path.is_file():
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries
