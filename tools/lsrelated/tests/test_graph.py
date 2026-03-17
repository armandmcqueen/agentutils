"""Tests for graph building and file matching logic."""

from collections import Counter
from pathlib import Path

from ccdata import (
    Session,
    Turn,
    AssistantResponse,
    ToolCall,
    Usage,
)
from lsrelated.graph import (
    build_undirected_graph,
    find_file,
    find_display_prefix,
    strip_prefix,
)


def _make_session(turns: list[Turn]) -> Session:
    return Session(
        session_id="test",
        project_key="-test",
        file_path=Path("/tmp/test.jsonl"),
        turns=turns,
    )


def _make_turn(tool_calls: list[ToolCall], index: int = 0) -> Turn:
    return Turn(
        index=index,
        user_text="test",
        timestamp=None,
        responses=[
            AssistantResponse(
                request_id=None, model=None, stop_reason=None,
                usage=Usage(), text_blocks=[], tool_calls=tool_calls,
                thinking_blocks=[], timestamp=None,
            )
        ],
    )


def _read_call(path: str) -> ToolCall:
    return ToolCall(name="Read", tool_use_id="t", input={"file_path": path})


def _write_call(path: str) -> ToolCall:
    return ToolCall(name="Write", tool_use_id="t", input={"file_path": path})


def _edit_call(path: str) -> ToolCall:
    return ToolCall(name="Edit", tool_use_id="t", input={"file_path": path})


def _bash_call(cmd: str) -> ToolCall:
    return ToolCall(name="Bash", tool_use_id="t", input={"command": cmd})


class TestBuildUndirectedGraph:
    def test_empty_sessions(self):
        edges, counts = build_undirected_graph([])
        assert edges == {}
        assert len(counts) == 0

    def test_single_file_no_edges(self):
        turn = _make_turn([_read_call("/a.py")])
        session = _make_session([turn])
        edges, counts = build_undirected_graph([session])
        assert edges == {}
        assert counts["/a.py"] == 1

    def test_two_files_one_edge(self):
        turn = _make_turn([_read_call("/a.py"), _read_call("/b.py")])
        session = _make_session([turn])
        edges, counts = build_undirected_graph([session])
        assert edges == {("/a.py", "/b.py"): 1}
        assert counts["/a.py"] == 1
        assert counts["/b.py"] == 1

    def test_canonical_order(self):
        """Edges always have the smaller path first."""
        turn = _make_turn([_read_call("/z.py"), _read_call("/a.py")])
        session = _make_session([turn])
        edges, _ = build_undirected_graph([session])
        assert ("/a.py", "/z.py") in edges

    def test_consecutive_dedup(self):
        """Consecutive reads of the same file are deduped."""
        turn = _make_turn([_read_call("/a.py"), _read_call("/a.py"), _read_call("/b.py")])
        session = _make_session([turn])
        edges, counts = build_undirected_graph([session])
        assert edges == {("/a.py", "/b.py"): 1}
        assert counts["/a.py"] == 1  # deduped to one

    def test_non_consecutive_not_deduped(self):
        """Non-consecutive reads of the same file are kept (but self-edges filtered)."""
        turn = _make_turn([
            _read_call("/a.py"), _read_call("/b.py"), _read_call("/a.py"),
        ])
        session = _make_session([turn])
        edges, counts = build_undirected_graph([session])
        # a appears twice (non-consecutive), b appears once
        assert counts["/a.py"] == 2
        assert counts["/b.py"] == 1
        # Edge (a, b) exists, no self-edge
        assert ("/a.py", "/b.py") in edges
        assert ("/a.py", "/a.py") not in edges

    def test_write_and_edit_included(self):
        turn = _make_turn([_write_call("/a.py"), _edit_call("/b.py")])
        session = _make_session([turn])
        edges, _ = build_undirected_graph([session])
        assert ("/a.py", "/b.py") in edges

    def test_bash_excluded(self):
        turn = _make_turn([_read_call("/a.py"), _bash_call("ls"), _read_call("/b.py")])
        session = _make_session([turn])
        edges, counts = build_undirected_graph([session])
        assert "ls" not in counts
        assert ("/a.py", "/b.py") in edges

    def test_weight_accumulates_across_turns(self):
        t1 = _make_turn([_read_call("/a.py"), _read_call("/b.py")], index=0)
        t2 = _make_turn([_read_call("/a.py"), _read_call("/b.py")], index=1)
        session = _make_session([t1, t2])
        edges, _ = build_undirected_graph([session])
        assert edges[("/a.py", "/b.py")] == 2

    def test_weight_accumulates_across_sessions(self):
        t1 = _make_turn([_read_call("/a.py"), _read_call("/b.py")])
        s1 = _make_session([t1])
        t2 = _make_turn([_read_call("/a.py"), _read_call("/b.py")])
        s2 = _make_session([t2])
        edges, _ = build_undirected_graph([s1, s2])
        assert edges[("/a.py", "/b.py")] == 2

    def test_pair_dedup_within_turn(self):
        """Same pair only counted once per turn even if files appear multiple times."""
        turn = _make_turn([
            _read_call("/a.py"), _read_call("/b.py"),
            _read_call("/c.py"), _read_call("/a.py"),
        ])
        session = _make_session([turn])
        edges, _ = build_undirected_graph([session])
        # (a, b) should appear once for this turn
        assert edges[("/a.py", "/b.py")] == 1

    def test_empty_file_path_skipped(self):
        turn = _make_turn([
            ToolCall(name="Read", tool_use_id="t", input={"file_path": ""}),
            _read_call("/a.py"),
        ])
        session = _make_session([turn])
        _, counts = build_undirected_graph([session])
        assert "" not in counts
        assert counts["/a.py"] == 1


class TestFindFile:
    def test_exact_match(self):
        counts = Counter({"/foo/bar.py": 5, "/baz/bar.py": 3})
        assert find_file("/foo/bar.py", counts) == "/foo/bar.py"

    def test_suffix_match_single(self):
        counts = Counter({"/foo/bar/types.ts": 5})
        assert find_file("types.ts", counts) == "/foo/bar/types.ts"

    def test_suffix_match_multiple_picks_highest(self):
        counts = Counter({"/foo/types.ts": 3, "/bar/types.ts": 10})
        assert find_file("types.ts", counts) == "/bar/types.ts"

    def test_substring_match_single(self):
        counts = Counter({"/foo/bar/types.ts": 5})
        assert find_file("bar/types", counts) == "/foo/bar/types.ts"

    def test_substring_match_multiple_picks_highest(self):
        counts = Counter({"/foo/utils.py": 2, "/bar/utils.py": 8})
        assert find_file("utils.py", counts) == "/bar/utils.py"

    def test_no_match(self):
        counts = Counter({"/foo/bar.py": 5})
        assert find_file("nonexistent.py", counts) is None

    def test_empty_counts(self):
        assert find_file("anything", Counter()) is None


class TestFindDisplayPrefix:
    def test_empty(self):
        assert find_display_prefix([]) == ""

    def test_common_prefix(self):
        files = [
            "/Users/me/code/proj/src/a.py",
            "/Users/me/code/proj/src/b.py",
            "/Users/me/code/proj/tests/c.py",
        ]
        prefix = find_display_prefix(files)
        assert prefix.startswith("/Users/me/code/")

    def test_outlier_ignored(self):
        """A single outlier file shouldn't break the prefix."""
        files = [
            "/Users/me/code/proj/src/a.py",
            "/Users/me/code/proj/src/b.py",
            "/Users/me/code/proj/src/c.py",
            "/home/other/.claude/plans/plan.md",
        ]
        prefix = find_display_prefix(files)
        # Should still find a prefix from the majority
        assert "proj" in prefix or "code" in prefix


class TestStripPrefix:
    def test_strips(self):
        assert strip_prefix("/foo/bar/baz.py", "/foo/bar/") == "baz.py"

    def test_no_match(self):
        assert strip_prefix("/other/baz.py", "/foo/bar/") == "/other/baz.py"

    def test_empty_prefix(self):
        assert strip_prefix("/foo/bar.py", "") == "/foo/bar.py"
