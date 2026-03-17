"""Tests for ccdata -- all against synthetic fixtures, no real data needed."""

import json
import pytest
from pathlib import Path

pd = pytest.importorskip("pandas")

from ccdata import (
    ClaudeCodeData,
    Compaction,
    Usage,
    ToolCall,
    TextBlock,
    ThinkingBlock,
    AssistantResponse,
    Turn,
    Session,
    parse_session,
    _is_user_text_entry,
    _get_user_text,
    _collect_tool_results,
)
from ccdata.testing import (
    user_text_entry,
    user_string_entry,
    user_tool_result_entry,
    assistant_entry,
    system_turn_duration,
    progress_entry,
    file_history_entry,
    progress_agent_entry,
    SessionBuilder,
    ClaudeDirBuilder,
)


# -- Fixture helpers (thin wrappers for backward compat within this file) --

_user_text_entry = user_text_entry
_user_string_entry = user_string_entry
_user_tool_result_entry = user_tool_result_entry
_assistant_entry = assistant_entry
_system_turn_duration = system_turn_duration
_progress_entry = progress_entry
_file_history_entry = file_history_entry


def _write_session(tmp_path: Path, entries: list[dict], session_id: str = "sess-001") -> Path:
    """Write entries as a JSONL file in a fake project directory and return the file path."""
    project_dir = tmp_path / "projects" / "-test-project"
    project_dir.mkdir(parents=True, exist_ok=True)
    fp = project_dir / f"{session_id}.jsonl"
    fp.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return fp


# -- Usage tests --


class TestUsage:
    def test_defaults(self):
        u = Usage()
        assert u.input_tokens == 0
        assert u.total_context == 0

    def test_total_context(self):
        u = Usage(input_tokens=10, cache_read_input_tokens=20, cache_creation_input_tokens=30)
        assert u.total_context == 60

    def test_from_raw(self):
        u = Usage.from_raw({
            "input_tokens": 5,
            "output_tokens": 10,
            "cache_read_input_tokens": 15,
            "cache_creation_input_tokens": 20,
            "service_tier": "standard",
        })
        assert u.input_tokens == 5
        assert u.output_tokens == 10
        assert u.cache_read_input_tokens == 15
        assert u.cache_creation_input_tokens == 20
        assert u.service_tier == "standard"
        assert u.total_context == 40

    def test_from_raw_none(self):
        u = Usage.from_raw(None)
        assert u.input_tokens == 0

    def test_from_raw_empty(self):
        u = Usage.from_raw({})
        assert u.input_tokens == 0
        assert u.service_tier is None


# -- ToolCall tests --


class TestToolCall:
    def test_summary_read(self):
        tc = ToolCall(name="Read", tool_use_id="t1", input={"file_path": "/foo/bar.py"})
        assert tc.summary == "/foo/bar.py"

    def test_summary_bash(self):
        tc = ToolCall(name="Bash", tool_use_id="t1", input={"command": "ls -la"})
        assert tc.summary == "ls -la"

    def test_summary_glob(self):
        tc = ToolCall(name="Glob", tool_use_id="t1", input={"pattern": "**/*.py"})
        assert tc.summary == "**/*.py"

    def test_summary_grep(self):
        tc = ToolCall(name="Grep", tool_use_id="t1", input={"pattern": "TODO"})
        assert tc.summary == "TODO"

    def test_summary_agent(self):
        tc = ToolCall(name="Agent", tool_use_id="t1", input={"description": "search for files"})
        assert tc.summary == "search for files"

    def test_summary_skill(self):
        tc = ToolCall(name="Skill", tool_use_id="t1", input={"skill": "commit"})
        assert tc.summary == "commit"

    def test_summary_unknown(self):
        tc = ToolCall(name="SomethingNew", tool_use_id="t1", input={"x": 1})
        assert tc.summary == ""

    def test_summary_bash_truncates(self):
        long_cmd = "x" * 200
        tc = ToolCall(name="Bash", tool_use_id="t1", input={"command": long_cmd})
        assert len(tc.summary) == 120


# -- Entry detection helpers --


class TestEntryHelpers:
    def test_is_user_text_entry_with_text_block(self):
        assert _is_user_text_entry(_user_text_entry("hello"))

    def test_is_user_text_entry_with_string(self):
        assert _is_user_text_entry(_user_string_entry("hello"))

    def test_is_user_text_entry_tool_result(self):
        assert not _is_user_text_entry(_user_tool_result_entry("t1", "ok"))

    def test_is_user_text_entry_assistant(self):
        assert not _is_user_text_entry(_assistant_entry([]))

    def test_get_user_text_block(self):
        assert _get_user_text(_user_text_entry("hello world")) == "hello world"

    def test_get_user_text_string(self):
        assert _get_user_text(_user_string_entry("hello")) == "hello"

    def test_get_user_text_empty(self):
        assert _get_user_text({"type": "user", "message": {"content": 42}}) == ""


class TestCollectToolResults:
    def test_basic(self):
        entries = [
            _user_tool_result_entry("tool-1", "result text"),
        ]
        results = _collect_tool_results(entries)
        assert results["tool-1"] == ("result text", False)

    def test_error(self):
        entries = [
            _user_tool_result_entry("tool-1", "error!", is_error=True),
        ]
        results = _collect_tool_results(entries)
        assert results["tool-1"] == ("error!", True)

    def test_list_content(self):
        entry = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool-2",
                        "content": [
                            {"type": "text", "text": "line1"},
                            {"type": "text", "text": "line2"},
                        ],
                    }
                ],
            },
        }
        results = _collect_tool_results([entry])
        assert results["tool-2"] == ("line1\nline2", False)

    def test_none_content(self):
        entry = {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "tool-3", "content": None},
                ],
            },
        }
        results = _collect_tool_results([entry])
        assert results["tool-3"] == ("", False)

    def test_skips_non_user_entries(self):
        results = _collect_tool_results([_assistant_entry([])])
        assert results == {}


# -- parse_session tests --


class TestParseSession:
    def test_minimal_session(self, tmp_path):
        entries = [
            _user_text_entry("Hello"),
            _assistant_entry([{"type": "text", "text": "Hi there!"}]),
            _system_turn_duration(3000),
        ]
        fp = _write_session(tmp_path, entries)
        s = parse_session(fp)

        assert s.session_id == "sess-001"
        assert s.project_key == "-test-project"
        assert s.version == "2.1.71"
        assert s.git_branch == "main"
        assert s.slug == "test-slug"
        assert s.raw_entry_count == 3
        assert s.turn_count == 1
        assert s.turns[0].user_text == "Hello"
        assert s.turns[0].text == "Hi there!"
        assert s.turns[0].duration_ms == 3000

    def test_multi_turn(self, tmp_path):
        entries = [
            _user_text_entry("Turn 1", timestamp="2026-03-01T00:00:00Z"),
            _assistant_entry([{"type": "text", "text": "Response 1"}], timestamp="2026-03-01T00:00:10Z"),
            _system_turn_duration(5000),
            _user_text_entry("Turn 2", timestamp="2026-03-01T00:01:00Z"),
            _assistant_entry([{"type": "text", "text": "Response 2"}], timestamp="2026-03-01T00:01:10Z"),
            _system_turn_duration(8000),
        ]
        fp = _write_session(tmp_path, entries)
        s = parse_session(fp)

        assert s.turn_count == 2
        assert s.turns[0].index == 0
        assert s.turns[0].user_text == "Turn 1"
        assert s.turns[1].index == 1
        assert s.turns[1].user_text == "Turn 2"
        assert s.turns[1].duration_ms == 8000

    def test_tool_use_and_result(self, tmp_path):
        entries = [
            _user_text_entry("Read a file"),
            _assistant_entry([
                {"type": "tool_use", "id": "tool-abc", "name": "Read", "input": {"file_path": "/tmp/x.py"}},
            ]),
            _user_tool_result_entry("tool-abc", "file contents here"),
            _assistant_entry([{"type": "text", "text": "I read the file."}]),
        ]
        fp = _write_session(tmp_path, entries)
        s = parse_session(fp)

        assert s.turn_count == 1
        tool_calls = s.turns[0].tool_calls
        assert len(tool_calls) == 1
        assert tool_calls[0].name == "Read"
        assert tool_calls[0].result == "file contents here"
        assert tool_calls[0].is_error is False
        assert tool_calls[0].summary == "/tmp/x.py"

    def test_tool_error(self, tmp_path):
        entries = [
            _user_text_entry("Do something"),
            _assistant_entry([
                {"type": "tool_use", "id": "tool-err", "name": "Bash", "input": {"command": "false"}},
            ]),
            _user_tool_result_entry("tool-err", "command failed", is_error=True),
            _assistant_entry([{"type": "text", "text": "That failed."}]),
        ]
        fp = _write_session(tmp_path, entries)
        s = parse_session(fp)

        tc = s.turns[0].tool_calls[0]
        assert tc.is_error is True
        assert tc.result == "command failed"

    def test_thinking_blocks(self, tmp_path):
        entries = [
            _user_text_entry("Think about this"),
            _assistant_entry([
                {"type": "thinking", "thinking": "", "signature": "sig123"},
                {"type": "text", "text": "Here's my answer."},
            ]),
        ]
        fp = _write_session(tmp_path, entries)
        s = parse_session(fp)

        r = s.turns[0].responses[0]
        assert len(r.thinking_blocks) == 1
        assert r.thinking_blocks[0].signature == "sig123"
        assert len(r.text_blocks) == 1

    def test_multiple_responses_per_turn(self, tmp_path):
        """Multiple assistant entries before the next user turn = multiple responses."""
        entries = [
            _user_text_entry("Do two things"),
            _assistant_entry(
                [{"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "/a"}}],
                request_id="req-1",
            ),
            _user_tool_result_entry("t1", "contents of a"),
            _assistant_entry(
                [{"type": "text", "text": "Done."}],
                request_id="req-2",
            ),
        ]
        fp = _write_session(tmp_path, entries)
        s = parse_session(fp)

        assert s.turn_count == 1
        assert len(s.turns[0].responses) == 2
        assert s.turns[0].responses[0].request_id == "req-1"
        assert s.turns[0].responses[1].request_id == "req-2"

    def test_metadata_extraction(self, tmp_path):
        entries = [
            _file_history_entry(),
            _user_text_entry("Hi", version="2.1.71", gitBranch="feat-x", slug="cool-slug"),
            _assistant_entry([{"type": "text", "text": "Hey"}]),
        ]
        # Manually add version/gitBranch/slug to the user entry at top level
        entries[1]["version"] = "2.1.71"
        entries[1]["gitBranch"] = "feat-x"
        entries[1]["slug"] = "cool-slug"

        fp = _write_session(tmp_path, entries)
        s = parse_session(fp)

        assert s.version == "2.1.71"
        assert s.git_branch == "feat-x"
        assert s.slug == "cool-slug"

    def test_skips_progress_and_file_history(self, tmp_path):
        entries = [
            _file_history_entry(),
            _progress_entry(),
            _user_text_entry("Hello"),
            _progress_entry(),
            _assistant_entry([{"type": "text", "text": "Hi"}]),
            _progress_entry(),
        ]
        fp = _write_session(tmp_path, entries)
        s = parse_session(fp)

        assert s.turn_count == 1
        assert s.raw_entry_count == 6

    def test_empty_file(self, tmp_path):
        fp = _write_session(tmp_path, [])
        s = parse_session(fp)
        assert s.turn_count == 0
        assert s.raw_entry_count == 0

    def test_malformed_lines_skipped(self, tmp_path):
        project_dir = tmp_path / "projects" / "-test-project"
        project_dir.mkdir(parents=True)
        fp = project_dir / "sess-bad.jsonl"
        fp.write_text(
            json.dumps(_user_text_entry("Hello")) + "\n"
            + "this is not json\n"
            + json.dumps(_assistant_entry([{"type": "text", "text": "Hi"}])) + "\n"
        )
        s = parse_session(fp)
        assert s.turn_count == 1
        assert s.raw_entry_count == 2

    def test_user_string_content_format(self, tmp_path):
        entries = [
            _user_string_entry("String format prompt"),
            _assistant_entry([{"type": "text", "text": "Response"}]),
        ]
        fp = _write_session(tmp_path, entries)
        s = parse_session(fp)

        assert s.turn_count == 1
        assert s.turns[0].user_text == "String format prompt"

    def test_assistant_before_any_user_is_ignored(self, tmp_path):
        entries = [
            _assistant_entry([{"type": "text", "text": "orphan response"}]),
            _user_text_entry("First real turn"),
            _assistant_entry([{"type": "text", "text": "real response"}]),
        ]
        fp = _write_session(tmp_path, entries)
        s = parse_session(fp)

        assert s.turn_count == 1
        assert s.turns[0].user_text == "First real turn"
        assert s.turns[0].text == "real response"

    def test_merge_subagents_false(self, tmp_path):
        """When merge_subagents=False, subagent tool calls are not merged."""
        entries = [
            _user_text_entry("Hello"),
            _assistant_entry([{"type": "text", "text": "Hi"}]),
        ]
        fp = _write_session(tmp_path, entries)
        # Should not raise even with merge_subagents=False
        s = parse_session(fp, merge_subagents=False)
        assert s.turn_count == 1


# -- Compaction detection tests --


class TestCompaction:
    def test_detects_context_drop(self, tmp_path):
        entries = [
            _user_text_entry("Turn 1", timestamp="2026-03-01T00:00:00Z"),
            _assistant_entry(
                [{"type": "text", "text": "R1"}],
                usage={"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 50000, "cache_creation_input_tokens": 50000},
                timestamp="2026-03-01T00:00:10Z",
            ),
            _system_turn_duration(5000),
            _user_text_entry("Turn 2", timestamp="2026-03-01T00:01:00Z"),
            # Context dropped from 100100 to 20000 (~80% drop)
            _assistant_entry(
                [{"type": "text", "text": "R2"}],
                usage={"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 10000, "cache_creation_input_tokens": 9900},
                timestamp="2026-03-01T00:01:10Z",
            ),
        ]
        fp = _write_session(tmp_path, entries)
        s = parse_session(fp)

        assert len(s.compactions) == 1
        c = s.compactions[0]
        assert c.pre_tokens == 100100
        assert c.post_tokens == 20000
        assert 0 < c.ratio < 0.8

    def test_no_false_compaction_on_normal_growth(self, tmp_path):
        entries = [
            _user_text_entry("Turn 1"),
            _assistant_entry(
                [{"type": "text", "text": "R1"}],
                usage={"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 1000},
            ),
            _system_turn_duration(),
            _user_text_entry("Turn 2"),
            _assistant_entry(
                [{"type": "text", "text": "R2"}],
                usage={"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 2000, "cache_creation_input_tokens": 2000},
            ),
        ]
        fp = _write_session(tmp_path, entries)
        s = parse_session(fp)
        assert len(s.compactions) == 0


# -- Session property tests --


class TestSessionProperties:
    @pytest.fixture
    def sample_session(self, tmp_path):
        entries = [
            _user_text_entry("Hello", timestamp="2026-03-01T00:00:00Z"),
            _assistant_entry(
                [
                    {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "/a"}},
                    {"type": "tool_use", "id": "t2", "name": "Read", "input": {"file_path": "/b"}},
                ],
                usage={"input_tokens": 10, "output_tokens": 20, "cache_read_input_tokens": 30, "cache_creation_input_tokens": 40},
                timestamp="2026-03-01T00:00:10Z",
            ),
            _user_tool_result_entry("t1", "ok"),
            _user_tool_result_entry("t2", "ok"),
            _assistant_entry(
                [
                    {"type": "tool_use", "id": "t3", "name": "Bash", "input": {"command": "ls"}},
                ],
                usage={"input_tokens": 5, "output_tokens": 15, "cache_read_input_tokens": 25, "cache_creation_input_tokens": 35},
                timestamp="2026-03-01T00:00:20Z",
            ),
            _user_tool_result_entry("t3", "file.txt"),
            _assistant_entry(
                [{"type": "text", "text": "Done"}],
                usage={"input_tokens": 3, "output_tokens": 8, "cache_read_input_tokens": 12, "cache_creation_input_tokens": 17},
                timestamp="2026-03-01T00:00:30Z",
            ),
            _system_turn_duration(30000),
            _user_text_entry("Bye", timestamp="2026-03-01T00:01:00Z"),
            _assistant_entry(
                [{"type": "text", "text": "Goodbye!"}],
                usage={"input_tokens": 2, "output_tokens": 5, "cache_read_input_tokens": 7, "cache_creation_input_tokens": 9},
                timestamp="2026-03-01T00:01:10Z",
            ),
            _system_turn_duration(10000),
        ]
        fp = _write_session(tmp_path, entries)
        return parse_session(fp)

    def test_turn_count(self, sample_session):
        assert sample_session.turn_count == 2

    def test_first_last_timestamp(self, sample_session):
        assert sample_session.first_timestamp == "2026-03-01T00:00:00Z"
        assert sample_session.last_timestamp == "2026-03-01T00:01:00Z"

    def test_duration_s(self, sample_session):
        assert sample_session.duration_s == 60.0

    def test_total_tool_calls(self, sample_session):
        assert sample_session.total_tool_calls == 3

    def test_tool_counts(self, sample_session):
        counts = sample_session.tool_counts
        assert counts == {"Read": 2, "Bash": 1}

    def test_total_usage(self, sample_session):
        u = sample_session.total_usage
        assert u.input_tokens == 10 + 5 + 3 + 2
        assert u.output_tokens == 20 + 15 + 8 + 5

    def test_project_name(self, sample_session):
        assert "test" in sample_session.project_name
        assert "-" not in sample_session.project_name.strip("/")

    def test_turn_usage_aggregation(self, sample_session):
        t0 = sample_session.turns[0]
        u = t0.usage
        # 3 responses in turn 0
        assert u.input_tokens == 10 + 5 + 3
        assert u.output_tokens == 20 + 15 + 8


# -- Turn property tests --


class TestTurnProperties:
    def test_text_concatenation(self):
        t = Turn(
            index=0,
            user_text="hi",
            timestamp=None,
            responses=[
                AssistantResponse(
                    request_id=None, model=None, stop_reason=None, usage=Usage(),
                    text_blocks=[TextBlock("aaa")], tool_calls=[], thinking_blocks=[], timestamp=None,
                ),
                AssistantResponse(
                    request_id=None, model=None, stop_reason=None, usage=Usage(),
                    text_blocks=[TextBlock("bbb")], tool_calls=[], thinking_blocks=[], timestamp=None,
                ),
            ],
        )
        assert t.text == "aaa\nbbb"

    def test_repr(self):
        t = Turn(index=3, user_text="Hello world", timestamp=None)
        r = repr(t)
        assert "Turn(3" in r
        assert "0 tools" in r
        assert "Hello world" in r


# -- ClaudeCodeData tests --


class TestClaudeCodeData:
    @pytest.fixture
    def data_dir(self, tmp_path):
        """Create a fake claude dir with two projects and a few sessions."""
        proj_a = tmp_path / "projects" / "-Users-me-code-alpha"
        proj_b = tmp_path / "projects" / "-Users-me-code-beta"
        proj_a.mkdir(parents=True)
        proj_b.mkdir(parents=True)

        # Project alpha: 2 sessions
        for sid, branch in [("aaa-111", "main"), ("aaa-222", "feat")]:
            entries = [
                {**_user_text_entry(f"Prompt in {sid}"), "gitBranch": branch},
                _assistant_entry([{"type": "text", "text": f"Reply in {sid}"}]),
            ]
            (proj_a / f"{sid}.jsonl").write_text(
                "\n".join(json.dumps(e) for e in entries) + "\n"
            )

        # Project beta: 1 session
        entries = [
            {**_user_text_entry("Beta prompt"), "gitBranch": "dev"},
            _assistant_entry([{"type": "text", "text": "Beta reply"}]),
        ]
        (proj_b / "bbb-111.jsonl").write_text(
            "\n".join(json.dumps(e) for e in entries) + "\n"
        )

        return tmp_path

    def test_no_filter(self, data_dir):
        cc = ClaudeCodeData(claude_dir=data_dir)
        assert len(cc.project_keys) == 2
        assert cc.session_count == 3

    def test_project_filter(self, data_dir):
        cc = ClaudeCodeData(project="alpha", claude_dir=data_dir)
        assert len(cc.project_keys) == 1
        assert cc.session_count == 2

    def test_project_filter_case_insensitive(self, data_dir):
        cc = ClaudeCodeData(project="BETA", claude_dir=data_dir)
        assert cc.session_count == 1

    def test_session_ids(self, data_dir):
        cc = ClaudeCodeData(claude_dir=data_dir)
        ids = cc.session_ids
        assert "aaa-111" in ids
        assert "aaa-222" in ids
        assert "bbb-111" in ids

    def test_projects_map(self, data_dir):
        cc = ClaudeCodeData(claude_dir=data_dir)
        projects = cc.projects
        assert len(projects) == 2
        alpha_key = [k for k in projects if "alpha" in k][0]
        assert set(projects[alpha_key]) == {"aaa-111", "aaa-222"}

    def test_load_session(self, data_dir):
        cc = ClaudeCodeData(claude_dir=data_dir)
        s = cc.session("aaa-111")
        assert s.session_id == "aaa-111"
        assert s.turn_count == 1
        assert s.turns[0].user_text == "Prompt in aaa-111"

    def test_session_caching(self, data_dir):
        cc = ClaudeCodeData(claude_dir=data_dir)
        s1 = cc.session("aaa-111")
        s2 = cc.session("aaa-111")
        assert s1 is s2

    def test_session_not_found(self, data_dir):
        cc = ClaudeCodeData(claude_dir=data_dir)
        with pytest.raises(FileNotFoundError):
            cc.session("nonexistent")

    def test_sessions_all(self, data_dir):
        cc = ClaudeCodeData(claude_dir=data_dir)
        all_sessions = cc.sessions()
        assert len(all_sessions) == 3

    def test_sessions_limit(self, data_dir):
        cc = ClaudeCodeData(claude_dir=data_dir)
        limited = cc.sessions(limit=2)
        assert len(limited) == 2

    def test_sessions_by_branch(self, data_dir):
        cc = ClaudeCodeData(project="alpha", claude_dir=data_dir)
        by_branch = cc.sessions_by_branch()
        assert "main" in by_branch
        assert "feat" in by_branch
        assert len(by_branch["main"]) == 1
        assert len(by_branch["feat"]) == 1

    def test_summary(self, data_dir):
        cc = ClaudeCodeData(claude_dir=data_dir)
        s = cc.summary()
        assert "2 project(s)" in s
        assert "2 sessions" in s
        assert "1 sessions" in s

    def test_repr(self, data_dir):
        cc = ClaudeCodeData(project="alpha", claude_dir=data_dir)
        r = repr(cc)
        assert "2 sessions" in r
        assert "alpha" in r

    def test_empty_dir(self, tmp_path):
        cc = ClaudeCodeData(claude_dir=tmp_path)
        assert cc.session_count == 0
        assert cc.project_keys == []

    def test_nonexistent_dir(self, tmp_path):
        cc = ClaudeCodeData(claude_dir=tmp_path / "nope")
        assert cc.session_count == 0

    def test_merge_subagents_false(self, data_dir):
        """ClaudeCodeData passes merge_subagents through to parse_session."""
        cc = ClaudeCodeData(claude_dir=data_dir, merge_subagents=False)
        s = cc.session("aaa-111")
        assert s.turn_count == 1


# -- AssistantResponse property tests --


class TestAssistantResponse:
    def test_text_property(self):
        r = AssistantResponse(
            request_id="r1", model="m", stop_reason="end_turn", usage=Usage(),
            text_blocks=[TextBlock("Hello"), TextBlock("World")],
            tool_calls=[], thinking_blocks=[], timestamp=None,
        )
        assert r.text == "Hello\nWorld"

    def test_tool_names(self):
        r = AssistantResponse(
            request_id="r1", model="m", stop_reason="end_turn", usage=Usage(),
            text_blocks=[],
            tool_calls=[
                ToolCall(name="Read", tool_use_id="t1", input={}),
                ToolCall(name="Bash", tool_use_id="t2", input={}),
            ],
            thinking_blocks=[], timestamp=None,
        )
        assert r.tool_names == ["Read", "Bash"]


# -- Session repr --


class TestSessionRepr:
    def test_repr_with_branch(self):
        s = Session(
            session_id="abcdef12-3456-7890-abcd-ef1234567890",
            project_key="-test",
            file_path=Path("/tmp/test.jsonl"),
            turns=[Turn(index=0, user_text="hi", timestamp="2026-03-01T00:00:00Z")],
            git_branch="main",
        )
        r = repr(s)
        assert "abcdef12.." in r
        assert "[main]" in r
        assert "1 turns" in r

    def test_repr_without_branch(self):
        s = Session(
            session_id="abcdef12-xxxx",
            project_key="-test",
            file_path=Path("/tmp/test.jsonl"),
            turns=[],
        )
        r = repr(s)
        assert "[" not in r
        assert "0 turns" in r

    def test_duration_none_without_timestamps(self):
        s = Session(
            session_id="x", project_key="-t", file_path=Path("/tmp/x"),
            turns=[Turn(index=0, user_text="hi", timestamp=None)],
        )
        assert s.duration_s is None


# -- DataFrame tests --


def _make_rich_data_dir(tmp_path):
    """Create a fixture with enough structure to exercise all DataFrame builders."""
    proj = tmp_path / "projects" / "-Users-me-code-myproj"
    proj.mkdir(parents=True)

    # Session 1: 2 turns, tool calls, compaction
    entries_1 = [
        _user_text_entry("First prompt", timestamp="2026-03-01T00:00:00Z"),
        _assistant_entry(
            [
                {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "/a.py"}},
                {"type": "text", "text": "Reading file..."},
            ],
            usage={"input_tokens": 10, "output_tokens": 20, "cache_read_input_tokens": 50000, "cache_creation_input_tokens": 50000},
            request_id="req-1a",
            timestamp="2026-03-01T00:00:10Z",
        ),
        _user_tool_result_entry("t1", "file contents"),
        _assistant_entry(
            [{"type": "text", "text": "Here's what I found."}],
            usage={"input_tokens": 15, "output_tokens": 30, "cache_read_input_tokens": 55000, "cache_creation_input_tokens": 55000},
            request_id="req-1b",
            timestamp="2026-03-01T00:00:20Z",
        ),
        _system_turn_duration(20000),
        _user_text_entry("Second prompt", timestamp="2026-03-01T00:01:00Z"),
        # Context drop: 110015 -> 15000 (compaction)
        _assistant_entry(
            [
                {"type": "thinking", "thinking": "", "signature": "sig1"},
                {"type": "tool_use", "id": "t2", "name": "Bash", "input": {"command": "echo hi"}},
            ],
            usage={"input_tokens": 5, "output_tokens": 10, "cache_read_input_tokens": 5000, "cache_creation_input_tokens": 9995},
            request_id="req-1c",
            timestamp="2026-03-01T00:01:10Z",
        ),
        _user_tool_result_entry("t2", "hi", is_error=False),
        _assistant_entry(
            [{"type": "text", "text": "Done."}],
            usage={"input_tokens": 8, "output_tokens": 12, "cache_read_input_tokens": 6000, "cache_creation_input_tokens": 10000},
            request_id="req-1d",
            timestamp="2026-03-01T00:01:30Z",
        ),
        _system_turn_duration(30000),
    ]
    (proj / "sess-rich-1.jsonl").write_text(
        "\n".join(json.dumps(e) for e in entries_1) + "\n"
    )

    # Session 2: 1 turn, no tools
    entries_2 = [
        {**_user_text_entry("Simple question", timestamp="2026-03-02T00:00:00Z"), "gitBranch": "feat"},
        _assistant_entry(
            [{"type": "text", "text": "Simple answer."}],
            usage={"input_tokens": 5, "output_tokens": 40, "cache_read_input_tokens": 100, "cache_creation_input_tokens": 200},
            timestamp="2026-03-02T00:00:05Z",
        ),
        _system_turn_duration(5000),
    ]
    (proj / "sess-rich-2.jsonl").write_text(
        "\n".join(json.dumps(e) for e in entries_2) + "\n"
    )

    return tmp_path


class TestSessionsDF:
    @pytest.fixture
    def cc(self, tmp_path):
        return ClaudeCodeData(claude_dir=_make_rich_data_dir(tmp_path))

    def test_shape(self, cc):
        df = cc.sessions_df()
        assert len(df) == 2
        assert "session_id" in df.columns
        assert "output_tokens" in df.columns

    def test_columns_present(self, cc):
        df = cc.sessions_df()
        expected = {
            "session_id", "project_key", "git_branch", "version", "slug",
            "turn_count", "total_tool_calls", "compaction_count",
            "first_timestamp", "last_timestamp", "duration_s",
            "input_tokens", "output_tokens", "cache_read_tokens",
            "cache_create_tokens", "total_context", "raw_entry_count",
        }
        assert expected.issubset(set(df.columns))

    def test_timestamp_dtype(self, cc):
        df = cc.sessions_df()
        assert pd.api.types.is_datetime64_any_dtype(df["first_timestamp"])

    def test_values(self, cc):
        df = cc.sessions_df()
        s1 = df[df["session_id"] == "sess-rich-1"].iloc[0]
        assert s1["turn_count"] == 2
        assert s1["total_tool_calls"] == 2  # Read + Bash

    def test_limit(self, cc):
        df = cc.sessions_df(limit=1)
        assert len(df) == 1

    def test_empty(self, tmp_path):
        cc = ClaudeCodeData(claude_dir=tmp_path)
        df = cc.sessions_df()
        assert len(df) == 0


class TestTurnsDF:
    @pytest.fixture
    def cc(self, tmp_path):
        return ClaudeCodeData(claude_dir=_make_rich_data_dir(tmp_path))

    def test_shape(self, cc):
        df = cc.turns_df()
        assert len(df) == 3  # 2 turns in sess-1 + 1 turn in sess-2

    def test_columns_present(self, cc):
        df = cc.turns_df()
        expected = {
            "session_id", "git_branch", "turn_index", "timestamp",
            "user_text", "user_text_len", "assistant_text_len",
            "response_count", "tool_call_count", "tool_names",
            "duration_ms", "had_compaction",
            "input_tokens", "output_tokens", "cache_read_tokens", "cache_create_tokens",
        }
        assert expected.issubset(set(df.columns))

    def test_user_text_preserved(self, cc):
        df = cc.turns_df()
        texts = df["user_text"].tolist()
        assert "First prompt" in texts
        assert "Second prompt" in texts
        assert "Simple question" in texts

    def test_tool_names_is_list(self, cc):
        df = cc.turns_df()
        row = df[df["user_text"] == "First prompt"].iloc[0]
        assert isinstance(row["tool_names"], list)
        assert "Read" in row["tool_names"]

    def test_timestamp_dtype(self, cc):
        df = cc.turns_df()
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])

    def test_had_compaction(self, cc):
        df = cc.turns_df()
        compacted = df[df["had_compaction"]]
        assert len(compacted) == 1


class TestToolCallsDF:
    @pytest.fixture
    def cc(self, tmp_path):
        return ClaudeCodeData(claude_dir=_make_rich_data_dir(tmp_path))

    def test_shape(self, cc):
        df = cc.tool_calls_df()
        assert len(df) == 2  # Read + Bash

    def test_columns_present(self, cc):
        df = cc.tool_calls_df()
        expected = {
            "session_id", "git_branch", "turn_index", "tool_name",
            "summary", "is_error", "has_result", "result_len", "input_keys",
        }
        assert expected.issubset(set(df.columns))

    def test_tool_names(self, cc):
        df = cc.tool_calls_df()
        names = df["tool_name"].tolist()
        assert "Read" in names
        assert "Bash" in names

    def test_summary_populated(self, cc):
        df = cc.tool_calls_df()
        read_row = df[df["tool_name"] == "Read"].iloc[0]
        assert read_row["summary"] == "/a.py"
        bash_row = df[df["tool_name"] == "Bash"].iloc[0]
        assert bash_row["summary"] == "echo hi"

    def test_results_populated(self, cc):
        df = cc.tool_calls_df()
        read_row = df[df["tool_name"] == "Read"].iloc[0]
        assert bool(read_row["has_result"]) is True
        assert read_row["result_len"] > 0

    def test_empty(self, tmp_path):
        cc = ClaudeCodeData(claude_dir=tmp_path)
        df = cc.tool_calls_df()
        assert len(df) == 0


class TestResponsesDF:
    @pytest.fixture
    def cc(self, tmp_path):
        return ClaudeCodeData(claude_dir=_make_rich_data_dir(tmp_path))

    def test_shape(self, cc):
        df = cc.responses_df()
        # sess-1: 4 responses (req-1a, req-1b, req-1c, req-1d), sess-2: 1
        assert len(df) == 5

    def test_columns_present(self, cc):
        df = cc.responses_df()
        expected = {
            "session_id", "git_branch", "turn_index", "response_index",
            "request_id", "model", "stop_reason", "timestamp",
            "text_block_count", "tool_call_count", "thinking_block_count",
            "text_len", "input_tokens", "output_tokens",
            "cache_read_tokens", "cache_create_tokens", "total_context",
        }
        assert expected.issubset(set(df.columns))

    def test_thinking_block_count(self, cc):
        df = cc.responses_df()
        req_c = df[df["request_id"] == "req-1c"].iloc[0]
        assert req_c["thinking_block_count"] == 1

    def test_total_context(self, cc):
        df = cc.responses_df()
        req_a = df[df["request_id"] == "req-1a"].iloc[0]
        assert req_a["total_context"] == 10 + 50000 + 50000

    def test_timestamp_dtype(self, cc):
        df = cc.responses_df()
        assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])


class TestCompactionsDF:
    @pytest.fixture
    def cc(self, tmp_path):
        return ClaudeCodeData(claude_dir=_make_rich_data_dir(tmp_path))

    def test_shape(self, cc):
        df = cc.compactions_df()
        assert len(df) == 1

    def test_columns_present(self, cc):
        df = cc.compactions_df()
        expected = {
            "session_id", "git_branch", "turn_index", "timestamp",
            "pre_tokens", "post_tokens", "ratio",
        }
        assert expected.issubset(set(df.columns))

    def test_values(self, cc):
        df = cc.compactions_df()
        row = df.iloc[0]
        assert row["pre_tokens"] > row["post_tokens"]
        assert 0 < row["ratio"] < 1

    def test_empty_when_no_compactions(self, tmp_path):
        proj = tmp_path / "projects" / "-Users-me-code-simple"
        proj.mkdir(parents=True)
        entries = [
            _user_text_entry("Hi"),
            _assistant_entry([{"type": "text", "text": "Hello"}]),
        ]
        (proj / "sess-simple.jsonl").write_text(
            "\n".join(json.dumps(e) for e in entries) + "\n"
        )
        cc = ClaudeCodeData(claude_dir=tmp_path)
        df = cc.compactions_df()
        assert len(df) == 0


# -- Subagent merging integration tests --


class TestSubagentMerging:
    """Tests that exercise subagent merging with actual files on disk."""

    def test_subagent_tools_merged_into_parent(self, tmp_path):
        """Subagent Read calls appear in parent turn when merge_subagents=True."""
        builder = (
            SessionBuilder()
            .add_subagent_turn(
                "Research this",
                agent_description="find files",
                subagent_file_reads=["/sub/a.py", "/sub/b.py"],
            )
        )
        claude_dir = ClaudeDirBuilder(tmp_path).add_session(builder).build()
        cc = ClaudeCodeData(claude_dir=claude_dir, merge_subagents=True)
        s = cc.session("sess-001")

        assert s.turn_count == 1
        tool_names = s.turns[0].tool_names
        # Should have Agent + 2 subagent Reads
        assert "Agent" in tool_names
        assert tool_names.count("Read") == 2

        # Verify the subagent reads have correct file paths
        read_calls = [tc for tc in s.turns[0].tool_calls if tc.name == "Read"]
        read_paths = {tc.input["file_path"] for tc in read_calls}
        assert read_paths == {"/sub/a.py", "/sub/b.py"}

    def test_subagent_tools_excluded_when_disabled(self, tmp_path):
        """Subagent tool calls are NOT present when merge_subagents=False."""
        builder = (
            SessionBuilder()
            .add_subagent_turn(
                "Research this",
                agent_description="find files",
                subagent_file_reads=["/sub/a.py"],
            )
        )
        claude_dir = ClaudeDirBuilder(tmp_path).add_session(builder).build()
        cc = ClaudeCodeData(claude_dir=claude_dir, merge_subagents=False)
        s = cc.session("sess-001")

        tool_names = s.turns[0].tool_names
        assert "Agent" in tool_names
        # No subagent reads should be merged
        assert "Read" not in tool_names

    def test_multiple_subagents(self, tmp_path):
        """Turn with a subagent + parent reads, both sets merged correctly."""
        builder = (
            SessionBuilder()
            .add_subagent_turn(
                "Do research",
                agent_description="search codebase",
                subagent_file_reads=["/sub/x.py"],
                parent_file_reads=["/parent/main.py"],
            )
        )
        claude_dir = ClaudeDirBuilder(tmp_path).add_session(builder).build()
        cc = ClaudeCodeData(claude_dir=claude_dir, merge_subagents=True)
        s = cc.session("sess-001")

        tool_names = s.turns[0].tool_names
        assert "Agent" in tool_names
        read_calls = [tc for tc in s.turns[0].tool_calls if tc.name == "Read"]
        read_paths = {tc.input["file_path"] for tc in read_calls}
        # Both parent and subagent reads
        assert "/parent/main.py" in read_paths
        assert "/sub/x.py" in read_paths
