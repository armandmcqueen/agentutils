"""Tests for gitro.policy validation logic."""

import pytest

from gitro.policy import validate


class TestUnconditionallyAllowed:
    """Subcommands that should always be allowed."""

    @pytest.mark.parametrize("cmd", [
        ["log"],
        ["log", "--oneline", "-10"],
        ["diff"],
        ["diff", "HEAD~3"],
        ["diff", "--cached"],
        ["show", "HEAD"],
        ["status"],
        ["status", "-s"],
        ["blame", "file.py"],
        ["shortlog", "-sn"],
        ["describe", "--tags"],
        ["rev-parse", "HEAD"],
        ["rev-list", "--count", "HEAD"],
        ["cat-file", "-t", "HEAD"],
        ["ls-files"],
        ["ls-tree", "HEAD"],
        ["ls-remote", "origin"],
        ["name-rev", "HEAD"],
        ["for-each-ref", "--format=%(refname)"],
        ["grep", "pattern"],
        ["reflog"],
        ["diff-tree", "HEAD"],
        ["diff-files"],
        ["diff-index", "HEAD"],
        ["merge-base", "main", "feature"],
        ["count-objects", "-v"],
        ["fsck"],
        ["verify-commit", "HEAD"],
        ["verify-tag", "v1.0"],
        ["cherry", "main"],
        ["whatchanged"],
        ["range-diff", "main...feature"],
        ["version"],
        ["help"],
    ])
    def test_allowed(self, cmd):
        allowed, reason = validate(cmd)
        assert allowed, f"Expected {cmd} to be allowed, got: {reason}"


class TestExplicitlyBlocked:
    """Subcommands that should always be blocked."""

    @pytest.mark.parametrize("cmd", [
        ["commit", "-m", "test"],
        ["push"],
        ["push", "origin", "main"],
        ["pull"],
        ["fetch"],
        ["fetch", "origin"],
        ["merge", "feature"],
        ["rebase", "main"],
        ["reset", "--hard", "HEAD~1"],
        ["checkout", "main"],
        ["switch", "main"],
        ["restore", "file.py"],
        ["add", "."],
        ["add", "-A"],
        ["rm", "file.py"],
        ["mv", "a.py", "b.py"],
        ["clean", "-fd"],
        ["init"],
        ["clone", "url"],
        ["cherry-pick", "abc123"],
        ["revert", "HEAD"],
        ["bisect", "start"],
        ["am", "patch"],
        ["apply", "patch"],
        ["format-patch", "HEAD~3"],
        ["gc"],
        ["prune"],
        ["submodule", "update"],
        ["worktree", "add", "path"],
        ["notes", "add"],
        ["filter-branch"],
        ["replace", "abc", "def"],
    ])
    def test_blocked(self, cmd):
        allowed, reason = validate(cmd)
        assert not allowed
        assert "mutating" in reason or "blocked" in reason


class TestBranch:
    """Conditional: branch listing allowed, mutations blocked."""

    def test_bare_branch(self):
        assert validate(["branch"])[0]

    def test_branch_list(self):
        assert validate(["branch", "--list"])[0]

    def test_branch_verbose(self):
        assert validate(["branch", "-v"])[0]

    def test_branch_all(self):
        assert validate(["branch", "-a"])[0]

    def test_branch_remote(self):
        assert validate(["branch", "-r"])[0]

    @pytest.mark.parametrize("flag", [
        "-d", "-D", "--delete", "-m", "-M", "--move",
        "-c", "-C", "--copy", "--edit-description",
        "--set-upstream-to", "--unset-upstream",
    ])
    def test_branch_blocked_flags(self, flag):
        allowed, reason = validate(["branch", flag])
        assert not allowed
        assert "mutating" in reason

    def test_branch_set_upstream_to_with_value(self):
        allowed, reason = validate(["branch", "--set-upstream-to=origin/main"])
        assert not allowed


class TestTag:
    """Conditional: tag listing allowed, mutations blocked."""

    def test_bare_tag(self):
        assert validate(["tag"])[0]

    def test_tag_list(self):
        assert validate(["tag", "-l"])[0]

    def test_tag_list_long(self):
        assert validate(["tag", "--list"])[0]

    def test_tag_list_pattern(self):
        assert validate(["tag", "-l", "v*"])[0]

    @pytest.mark.parametrize("flag", [
        "-d", "--delete", "-a", "-s", "-f", "--force", "--create-reflog",
    ])
    def test_tag_blocked_flags(self, flag):
        allowed, reason = validate(["tag", flag])
        assert not allowed
        assert "mutating" in reason


class TestStash:
    """Conditional: stash list/show allowed, mutations blocked."""

    def test_stash_list(self):
        assert validate(["stash", "list"])[0]

    def test_stash_show(self):
        assert validate(["stash", "show"])[0]

    def test_stash_show_with_index(self):
        assert validate(["stash", "show", "stash@{0}"])[0]

    def test_bare_stash_blocked(self):
        allowed, reason = validate(["stash"])
        assert not allowed
        assert "push" in reason

    def test_stash_with_flags_blocked(self):
        allowed, reason = validate(["stash", "-u"])
        assert not allowed

    @pytest.mark.parametrize("sub", ["pop", "drop", "apply", "push", "clear", "create", "store"])
    def test_stash_mutating_subs_blocked(self, sub):
        allowed, reason = validate(["stash", sub])
        assert not allowed
        assert "mutating" in reason


class TestRemote:
    """Conditional: remote listing allowed, mutations blocked."""

    def test_bare_remote(self):
        assert validate(["remote"])[0]

    def test_remote_verbose(self):
        assert validate(["remote", "-v"])[0]

    def test_remote_verbose_long(self):
        assert validate(["remote", "--verbose"])[0]

    def test_remote_show(self):
        assert validate(["remote", "show", "origin"])[0]

    def test_remote_get_url(self):
        assert validate(["remote", "get-url", "origin"])[0]

    @pytest.mark.parametrize("sub", ["add", "remove", "rename", "set-url", "set-head", "prune", "update"])
    def test_remote_blocked_subs(self, sub):
        allowed, reason = validate(["remote", sub])
        assert not allowed
        assert "mutating" in reason


class TestConfig:
    """Conditional: read-only config allowed, mutations blocked."""

    def test_config_get(self):
        assert validate(["config", "--get", "user.name"])[0]

    def test_config_get_all(self):
        assert validate(["config", "--get-all", "remote.origin.url"])[0]

    def test_config_get_regexp(self):
        assert validate(["config", "--get-regexp", "user.*"])[0]

    def test_config_list(self):
        assert validate(["config", "--list"])[0]

    def test_config_list_short(self):
        assert validate(["config", "-l"])[0]

    def test_config_bare_key(self):
        # `git config user.name` → prints the value, read-only
        assert validate(["config", "user.name"])[0]

    def test_bare_config_blocked(self):
        allowed, reason = validate(["config"])
        assert not allowed

    @pytest.mark.parametrize("flag", [
        "--add", "--unset", "--unset-all", "--replace-all",
        "--rename-section", "--remove-section", "--edit",
    ])
    def test_config_blocked_flags(self, flag):
        allowed, reason = validate(["config", flag])
        assert not allowed
        assert "mutating" in reason


class TestGlobalFlags:
    """Global git flags should be skipped to find the subcommand."""

    def test_no_pager(self):
        assert validate(["--no-pager", "log"])[0]

    def test_c_flag(self):
        assert validate(["-C", "/tmp", "status"])[0]

    def test_git_dir(self):
        assert validate(["--git-dir=/tmp/.git", "log"])[0]

    def test_work_tree(self):
        assert validate(["--work-tree", "/tmp", "status"])[0]

    def test_config_key_val(self):
        assert validate(["-c", "color.ui=false", "log"])[0]

    def test_bare_flag(self):
        assert validate(["--bare", "log"])[0]

    def test_multiple_global_flags(self):
        assert validate(["--no-pager", "-C", "/tmp", "log", "--oneline"])[0]

    def test_unknown_global_flag(self):
        allowed, reason = validate(["--unknown-flag", "log"])
        assert not allowed
        assert "Unknown global flag" in reason

    def test_global_flags_with_blocked_command(self):
        allowed, reason = validate(["--no-pager", "push"])
        assert not allowed


class TestEdgeCases:
    """Edge cases and error handling."""

    def test_empty_args(self):
        allowed, reason = validate([])
        assert not allowed
        assert "No git subcommand" in reason

    def test_only_global_flags(self):
        allowed, reason = validate(["--no-pager"])
        assert not allowed
        assert "No git subcommand" in reason

    def test_unknown_subcommand(self):
        allowed, reason = validate(["my-alias"])
        assert not allowed
        assert "Unknown" in reason

    def test_branch_set_upstream_equals_form(self):
        allowed, reason = validate(["branch", "--set-upstream-to=origin/main"])
        assert not allowed
