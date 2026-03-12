"""CLI entry point for gitro."""

import subprocess
import sys

from gitro.help import (
    COMMAND_HELP,
    TOOL_DESCRIPTION,
    TOOL_DESCRIPTION_SHORT,
    format_allowed_commands,
)
from gitro.policy import validate


def main() -> None:
    args = sys.argv[1:]

    # No args → print short help
    if not args:
        print(TOOL_DESCRIPTION_SHORT)
        sys.exit(0)

    # Meta-commands
    cmd = args[0]

    if cmd == "tool-description":
        print(TOOL_DESCRIPTION)
        return

    if cmd == "tool-description-short":
        print(TOOL_DESCRIPTION_SHORT)
        return

    if cmd == "allowed":
        print(format_allowed_commands())
        return

    if cmd == "help":
        if len(args) > 1 and args[1] in COMMAND_HELP:
            print(f"{args[1]}: {COMMAND_HELP[args[1]]}")
        else:
            print(TOOL_DESCRIPTION)
        return

    # Git passthrough
    allowed, reason = validate(args)
    if not allowed:
        print(f"gitro: blocked — {reason}", file=sys.stderr)
        sys.exit(1)

    result = subprocess.run(["git"] + args)
    sys.exit(result.returncode)
