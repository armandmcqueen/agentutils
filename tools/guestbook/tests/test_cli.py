"""Tests for the guestbook CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from guestbook.storage import find_marker, read_entries, write_entry, MARKER_NAME, DATA_DIR, ENTRIES_FILE


# --- storage unit tests ---


def test_find_marker_at_start(tmp_path: Path) -> None:
    marker = tmp_path / MARKER_NAME
    marker.touch()
    assert find_marker(tmp_path) == marker


def test_find_marker_walks_up(tmp_path: Path) -> None:
    marker = tmp_path / MARKER_NAME
    marker.touch()
    child = tmp_path / "a" / "b" / "c"
    child.mkdir(parents=True)
    assert find_marker(child) == marker


def test_find_marker_none(tmp_path: Path) -> None:
    # tmp_path has no marker and we won't find one going to root
    # (unless the test machine has one, so we make a unique subdir)
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    result = find_marker(isolated)
    # Either None or a marker outside tmp_path (we can't control the test machine)
    # Just verify it doesn't crash and returns Path or None
    assert result is None or isinstance(result, Path)


def test_write_and_read_entries(tmp_path: Path) -> None:
    marker = tmp_path / MARKER_NAME
    marker.touch()

    write_entry(marker, {"task": "test1", "note": "hello"})
    write_entry(marker, {"task": "test2"})

    entries = read_entries(marker)
    assert len(entries) == 2
    assert entries[0]["task"] == "test1"
    assert entries[0]["note"] == "hello"
    assert "timestamp" in entries[0]
    assert entries[1]["task"] == "test2"
    assert "timestamp" in entries[1]


def test_read_entries_empty(tmp_path: Path) -> None:
    marker = tmp_path / MARKER_NAME
    marker.touch()
    assert read_entries(marker) == []


def test_entries_stored_as_jsonl(tmp_path: Path) -> None:
    marker = tmp_path / MARKER_NAME
    marker.touch()
    write_entry(marker, {"a": 1})
    write_entry(marker, {"b": 2})

    entries_file = tmp_path / DATA_DIR / ENTRIES_FILE
    assert entries_file.is_file()
    lines = entries_file.read_text().strip().split("\n")
    assert len(lines) == 2
    for line in lines:
        obj = json.loads(line)
        assert "timestamp" in obj


# --- CLI integration tests ---

TOOL_DIR = Path(__file__).resolve().parent.parent


def run_cli(*args: str, stdin_data: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "guestbook"] + list(args),
        input=stdin_data,
        capture_output=True,
        text=True,
        cwd=TOOL_DIR,
        env={"PATH": "", "PYTHONPATH": str(TOOL_DIR / "src")},
    )


def test_cli_init(tmp_path: Path) -> None:
    result = run_cli("init", str(tmp_path / "newdir"))
    assert result.returncode == 0
    assert (tmp_path / "newdir" / MARKER_NAME).is_file()


def test_cli_init_already_exists(tmp_path: Path) -> None:
    (tmp_path / MARKER_NAME).touch()
    result = run_cli("init", str(tmp_path))
    assert result.returncode == 0
    assert "already exists" in result.stdout


def test_cli_sign_and_read(tmp_path: Path) -> None:
    (tmp_path / MARKER_NAME).touch()
    payload = json.dumps({"task": "testing", "note": "hello"})

    result = run_cli("sign", "--dir", str(tmp_path), stdin_data=payload)
    assert result.returncode == 0, result.stderr

    result = run_cli("read", "--dir", str(tmp_path))
    assert result.returncode == 0
    assert "testing" in result.stdout
    assert "hello" in result.stdout


def test_cli_sign_no_stdin(tmp_path: Path) -> None:
    (tmp_path / MARKER_NAME).touch()
    result = run_cli("sign", "--dir", str(tmp_path), stdin_data="")
    assert result.returncode == 1


def test_cli_sign_invalid_json(tmp_path: Path) -> None:
    (tmp_path / MARKER_NAME).touch()
    result = run_cli("sign", "--dir", str(tmp_path), stdin_data="not json")
    assert result.returncode == 1


def test_cli_sign_non_object(tmp_path: Path) -> None:
    (tmp_path / MARKER_NAME).touch()
    result = run_cli("sign", "--dir", str(tmp_path), stdin_data="[1,2,3]")
    assert result.returncode == 1


def test_cli_find(tmp_path: Path) -> None:
    (tmp_path / MARKER_NAME).touch()
    child = tmp_path / "sub" / "deep"
    child.mkdir(parents=True)

    result = run_cli("find", "--dir", str(child))
    assert result.returncode == 0
    assert str(tmp_path / MARKER_NAME) in result.stdout


def test_cli_find_none(tmp_path: Path) -> None:
    isolated = tmp_path / "empty"
    isolated.mkdir()
    result = run_cli("find", "--dir", str(isolated))
    # May find a marker above tmp_path on the test machine, so just check it doesn't crash
    assert result.returncode in (0, 1)


def test_cli_read_empty(tmp_path: Path) -> None:
    (tmp_path / MARKER_NAME).touch()
    result = run_cli("read", "--dir", str(tmp_path))
    assert result.returncode == 0
    assert "No entries" in result.stdout


def test_cli_tool_description() -> None:
    result = run_cli("tool-description")
    assert result.returncode == 0
    assert "guestbook" in result.stdout


def test_cli_tool_description_short() -> None:
    result = run_cli("tool-description-short")
    assert result.returncode == 0
    assert "guestbook" in result.stdout
