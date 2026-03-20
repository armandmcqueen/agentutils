#!/usr/bin/env python3
"""
Skill test harness — verifies that Claude Code skills change agent behavior.

For each scenario, runs a Claude subagent twice:
  1. WITHOUT skills (--disable-slash-commands) — baseline
  2. WITH skills enabled — should trigger tool usage

Compares whether the expected tool was invoked in the "with" run.

Usage:
    python3 tests/skill_tests/run_skill_tests.py
    python3 tests/skill_tests/run_skill_tests.py --scenario lsrelated
    python3 tests/skill_tests/run_skill_tests.py --with-only  # skip baseline (faster)
"""

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Scenario:
    """A test scenario for a skill."""

    skill: str
    prompt: str
    expected_tool: str  # substring to look for in Bash commands
    description: str


SCENARIOS = [
    Scenario(
        skill="lsrelated",
        prompt=(
            "I'm new to this codebase. I just opened tools/lsrelated/src/lsrelated/graph.py "
            "and I want to know what other files are closely coupled to it. What files should "
            "I read next?"
        ),
        expected_tool="lsrelated",
        description="Natural prompt: exploring coupled files in unfamiliar codebase",
    ),
    Scenario(
        skill="gitro",
        prompt=(
            "Show me the recent git history for this repo. I want to see what's been "
            "changed lately."
        ),
        expected_tool="gitro",
        description="Natural prompt: asking for git log without naming the tool",
    ),
    Scenario(
        skill="markdownpeek",
        prompt=(
            "The README.md in this repo looks pretty long. Can you give me an overview "
            "of its structure — what sections does it have?"
        ),
        expected_tool="markdownpeek",
        description="Natural prompt: asking about Markdown structure without naming the tool",
    ),
]


def run_claude(prompt: str, *, disable_skills: bool, max_turns: int = 3) -> list[dict]:
    """Run claude CLI and return parsed stream-json messages."""
    cmd = [
        "claude",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--dangerously-skip-permissions",
        "--max-turns",
        str(max_turns),
        "--model",
        "sonnet",
    ]
    if disable_skills:
        cmd.append("--disable-slash-commands")
    cmd.append(prompt)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(Path(__file__).resolve().parents[2]),  # repo root
    )

    messages = []
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return messages


def extract_bash_commands(messages: list[dict]) -> list[str]:
    """Extract all Bash command strings from stream-json messages."""
    commands = []
    for msg in messages:
        if msg.get("type") != "assistant":
            continue
        for content in msg.get("message", {}).get("content", []):
            if content.get("type") == "tool_use" and content.get("name") == "Bash":
                cmd = content.get("input", {}).get("command", "")
                if cmd:
                    commands.append(cmd)
    return commands


def extract_result_text(messages: list[dict]) -> str:
    """Extract the final result text."""
    for msg in messages:
        if msg.get("type") == "result":
            return msg.get("result", "")
    return ""


def check_tool_usage(commands: list[str], expected: str) -> bool:
    """Check if any Bash command contains the expected tool name."""
    return any(expected in cmd for cmd in commands)


def run_scenario(scenario: Scenario, *, skip_baseline: bool = False) -> dict:
    """Run a single test scenario and return results."""
    result = {
        "skill": scenario.skill,
        "description": scenario.description,
    }

    # Baseline (without skills)
    if not skip_baseline:
        print(f"  Running baseline (skills disabled)...", flush=True)
        try:
            baseline_msgs = run_claude(scenario.prompt, disable_skills=True)
            baseline_cmds = extract_bash_commands(baseline_msgs)
            baseline_used = check_tool_usage(baseline_cmds, scenario.expected_tool)
            result["baseline_commands"] = baseline_cmds
            result["baseline_used_tool"] = baseline_used
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT on baseline")
            result["baseline_commands"] = []
            result["baseline_used_tool"] = False
            result["baseline_timeout"] = True
    else:
        result["baseline_commands"] = []
        result["baseline_used_tool"] = None  # skipped

    # With skills
    print(f"  Running with skills enabled...", flush=True)
    try:
        skill_msgs = run_claude(scenario.prompt, disable_skills=False)
        skill_cmds = extract_bash_commands(skill_msgs)
        skill_used = check_tool_usage(skill_cmds, scenario.expected_tool)
        skill_result_text = extract_result_text(skill_msgs)
        result["skill_commands"] = skill_cmds
        result["skill_used_tool"] = skill_used
        result["skill_result_snippet"] = skill_result_text[:200]
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT with skills")
        result["skill_commands"] = []
        result["skill_used_tool"] = False
        result["skill_timeout"] = True

    return result


def main():
    parser = argparse.ArgumentParser(description="Skill test harness")
    parser.add_argument(
        "--scenario",
        help="Run only a specific scenario (by skill name)",
    )
    parser.add_argument(
        "--with-only",
        action="store_true",
        help="Skip baseline runs (faster)",
    )
    args = parser.parse_args()

    scenarios = SCENARIOS
    if args.scenario:
        scenarios = [s for s in SCENARIOS if s.skill == args.scenario]
        if not scenarios:
            print(f"Unknown scenario: {args.scenario}")
            print(f"Available: {', '.join(s.skill for s in SCENARIOS)}")
            sys.exit(1)

    print(f"Running {len(scenarios)} skill test(s)...\n")

    results = []
    for scenario in scenarios:
        print(f"[{scenario.skill}] {scenario.description}")
        result = run_scenario(scenario, skip_baseline=args.with_only)
        results.append(result)

        # Print summary
        if result.get("baseline_used_tool") is not None:
            baseline_str = "YES" if result["baseline_used_tool"] else "no"
            print(f"  Baseline used {scenario.expected_tool}: {baseline_str}")
            print(f"  Baseline commands: {result['baseline_commands']}")
        skill_str = "YES" if result["skill_used_tool"] else "no"
        print(f"  With-skill used {scenario.expected_tool}: {skill_str}")
        print(f"  With-skill commands: {result['skill_commands']}")

        if result["skill_used_tool"]:
            print(f"  -> PASS")
        elif result.get("baseline_used_tool") is None:
            print(f"  -> FAIL (tool not used with skills enabled)")
        elif not result["baseline_used_tool"] and not result["skill_used_tool"]:
            print(f"  -> FAIL (tool not used in either run)")
        else:
            print(f"  -> INCONCLUSIVE")
        print()

    # Summary
    passed = sum(1 for r in results if r["skill_used_tool"])
    total = len(results)
    print(f"Results: {passed}/{total} scenarios used expected tool with skills enabled")

    # Save detailed results
    output_path = Path(__file__).parent / "last_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Detailed results saved to {output_path}")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
