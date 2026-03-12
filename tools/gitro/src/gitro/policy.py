"""Allowlist-based validation for git subcommands."""

# Subcommands that are unconditionally allowed (any flags fine)
UNCONDITIONALLY_ALLOWED: set[str] = {
    "log", "diff", "show", "status", "blame", "shortlog", "describe",
    "rev-parse", "rev-list", "cat-file", "ls-files", "ls-tree", "ls-remote",
    "name-rev", "for-each-ref", "grep", "reflog", "diff-tree", "diff-files",
    "diff-index", "merge-base", "count-objects", "fsck", "verify-commit",
    "verify-tag", "cherry", "whatchanged", "range-diff", "version", "help",
}

# Subcommands that are explicitly blocked (clear error messages)
EXPLICITLY_BLOCKED: set[str] = {
    "commit", "push", "pull", "fetch", "merge", "rebase", "reset",
    "checkout", "switch", "restore", "add", "rm", "mv", "clean",
    "init", "clone", "cherry-pick", "revert", "bisect", "am", "apply",
    "format-patch", "send-email", "archive", "bundle", "gc", "prune",
    "pack-objects", "submodule", "worktree", "notes", "filter-branch",
    "replace",
}

# Flags that cause branch to mutate
_BRANCH_BLOCKED_FLAGS: set[str] = {
    "-d", "-D", "--delete",
    "-m", "-M", "--move",
    "-c", "-C", "--copy",
    "--edit-description", "--set-upstream-to", "--unset-upstream",
}

# Flags that cause tag to mutate
_TAG_BLOCKED_FLAGS: set[str] = {
    "-d", "--delete", "-a", "-s", "-f", "--force", "--create-reflog",
}

# Stash sub-subcommands that are allowed
_STASH_ALLOWED_SUBS: set[str] = {"list", "show"}

# Stash sub-subcommands that are blocked
_STASH_BLOCKED_SUBS: set[str] = {
    "pop", "drop", "apply", "push", "clear", "create", "store",
}

# Remote sub-subcommands that are allowed
_REMOTE_ALLOWED_SUBS: set[str] = {"show", "get-url"}

# Remote sub-subcommands that are blocked
_REMOTE_BLOCKED_SUBS: set[str] = {
    "add", "remove", "rename", "set-url", "set-head", "prune", "update",
}

# Config flags that are allowed (read-only)
_CONFIG_ALLOWED_FLAGS: set[str] = {
    "--get", "--get-all", "--get-regexp", "--list", "-l",
}

# Config flags that are blocked (mutating)
_CONFIG_BLOCKED_FLAGS: set[str] = {
    "--add", "--unset", "--unset-all", "--replace-all",
    "--rename-section", "--remove-section", "--edit",
}

# Global git flags that take no argument
_GLOBAL_FLAGS_NO_ARG: set[str] = {
    "--no-pager", "--bare", "--no-replace-objects",
    "--literal-pathspecs", "--glob-pathspecs",
    "--noglob-pathspecs", "--icase-pathspecs",
}

# Global git flags that take one argument (next token or =value)
_GLOBAL_FLAGS_WITH_ARG: set[str] = {
    "-C", "--git-dir", "--work-tree", "-c",
}


def _skip_global_flags(args: list[str]) -> tuple[list[str], str | None]:
    """Skip known global git flags to find the subcommand.

    Returns (remaining_args, error_message).
    If error_message is not None, the args are invalid.
    """
    i = 0
    while i < len(args):
        arg = args[i]

        # Not a flag → this is the subcommand
        if not arg.startswith("-"):
            return args[i:], None

        # No-arg global flags
        if arg in _GLOBAL_FLAGS_NO_ARG:
            i += 1
            continue

        # Flags with =value form
        matched_eq = False
        for flag in _GLOBAL_FLAGS_WITH_ARG:
            if arg == flag:
                # Next token is the value
                i += 2
                matched_eq = True
                break
            if arg.startswith(flag + "="):
                i += 1
                matched_eq = True
                break
        if matched_eq:
            continue

        # Unknown flag before subcommand
        return args[i:], f"Unknown global flag before subcommand: {arg}"

    return [], None


def _validate_branch(sub_args: list[str]) -> tuple[bool, str]:
    for arg in sub_args:
        if arg in _BRANCH_BLOCKED_FLAGS:
            return False, f"'git branch {arg}' is a mutating operation"
        if arg.startswith("--set-upstream-to="):
            return False, "'git branch --set-upstream-to' is a mutating operation"
    return True, ""


def _validate_tag(sub_args: list[str]) -> tuple[bool, str]:
    for arg in sub_args:
        if arg in _TAG_BLOCKED_FLAGS:
            return False, f"'git tag {arg}' is a mutating operation"
    return True, ""


def _validate_stash(sub_args: list[str]) -> tuple[bool, str]:
    if not sub_args:
        return False, "'git stash' with no arguments implies 'push', which is a mutating operation"

    sub_sub = sub_args[0]
    if sub_sub.startswith("-"):
        # flags to bare stash = stash push
        return False, "'git stash' with flags implies 'push', which is a mutating operation"

    if sub_sub in _STASH_ALLOWED_SUBS:
        return True, ""
    if sub_sub in _STASH_BLOCKED_SUBS:
        return False, f"'git stash {sub_sub}' is a mutating operation"
    return False, f"Unknown stash subcommand: '{sub_sub}'"


def _validate_remote(sub_args: list[str]) -> tuple[bool, str]:
    # bare `git remote` or `git remote -v` → listing
    if not sub_args:
        return True, ""
    if sub_args[0] in ("-v", "--verbose"):
        return True, ""

    sub_sub = sub_args[0]
    if sub_sub in _REMOTE_ALLOWED_SUBS:
        return True, ""
    if sub_sub in _REMOTE_BLOCKED_SUBS:
        return False, f"'git remote {sub_sub}' is a mutating operation"
    return False, f"Unknown remote subcommand: '{sub_sub}'"


def _validate_config(sub_args: list[str]) -> tuple[bool, str]:
    if not sub_args:
        return False, "'git config' with no arguments is not allowed; use --get, --list, etc."

    for arg in sub_args:
        if arg in _CONFIG_BLOCKED_FLAGS:
            return False, f"'git config {arg}' is a mutating operation"

    # Must have at least one allowed flag
    has_allowed = any(
        arg in _CONFIG_ALLOWED_FLAGS or arg.startswith("--get-regexp=")
        for arg in sub_args
    )
    if has_allowed:
        return True, ""

    # Positional-only config (e.g. `git config user.name`) is a read → allow
    # This is the `git config <key>` form which just prints the value
    if not any(arg.startswith("-") for arg in sub_args):
        return True, ""

    return False, "'git config' requires a read-only flag (--get, --list, -l, --get-all, --get-regexp)"


_CONDITIONAL_VALIDATORS: dict[str, callable] = {
    "branch": _validate_branch,
    "tag": _validate_tag,
    "stash": _validate_stash,
    "remote": _validate_remote,
    "config": _validate_config,
}


def validate(args: list[str]) -> tuple[bool, str]:
    """Validate a list of git arguments against the allowlist.

    Returns (allowed, reason). If allowed is False, reason explains why.
    """
    if not args:
        return False, "No git subcommand provided"

    remaining, error = _skip_global_flags(args)
    if error:
        return False, error

    if not remaining:
        # Only global flags, no subcommand
        return False, "No git subcommand provided"

    subcommand = remaining[0]
    sub_args = remaining[1:]

    if subcommand in UNCONDITIONALLY_ALLOWED:
        return True, ""

    if subcommand in _CONDITIONAL_VALIDATORS:
        return _CONDITIONAL_VALIDATORS[subcommand](sub_args)

    if subcommand in EXPLICITLY_BLOCKED:
        return False, f"'git {subcommand}' is a mutating operation and is blocked by gitro"

    return False, f"Unknown git subcommand: '{subcommand}' — gitro only allows known read-only commands"
