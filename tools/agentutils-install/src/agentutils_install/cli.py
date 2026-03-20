"""Installer for agentutils CLI tools and Claude Code skills."""

import shutil
import subprocess
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Install/uninstall agentutils CLI tools and Claude Code skills.")
console = Console()

# Tools to install (relative to repo root). Excludes agentutils-install itself.
TOOLS = ["gitro", "lsrelated", "markdownpeek"]

SKILLS_DIR_NAME = "skills"


def _repo_root() -> Path:
    """Find the repo root by walking up from this file's location."""
    # This file lives at tools/agentutils-install/src/agentutils_install/cli.py
    # Repo root is 5 levels up.
    candidate = Path(__file__).resolve().parents[4]
    if (candidate / "tools").is_dir() and (candidate / "CLAUDE.md").is_file():
        return candidate
    # Fallback: try git
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return Path(result.stdout.strip())
    raise typer.Exit(
        code=1,
    )


def _skills_target() -> Path:
    """Return the target directory for skills (~/.claude/skills/)."""
    return Path.home() / ".claude" / "skills"


def _run(cmd: list[str], label: str) -> bool:
    """Run a command, print status, return success."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        console.print(f"  [green]✓[/green] {label}")
        return True
    else:
        console.print(f"  [red]✗[/red] {label}")
        if result.stderr.strip():
            console.print(f"    {result.stderr.strip()}")
        return False


@app.command()
def install(
    force: bool = typer.Option(False, "--force", "-f", help="Force reinstall"),
) -> None:
    """Install all agentutils CLI tools via uv tool install."""
    root = _repo_root()
    console.print("[bold]Installing tools...[/bold]")
    for tool in TOOLS:
        tool_path = root / "tools" / tool
        if not tool_path.exists():
            console.print(f"  [red]✗[/red] {tool} — directory not found at {tool_path}")
            continue
        cmd = ["uv", "tool", "install", "--from", str(tool_path), tool]
        if force:
            cmd.append("--force")
        _run(cmd, tool)


@app.command()
def uninstall() -> None:
    """Uninstall all agentutils CLI tools."""
    console.print("[bold]Uninstalling tools...[/bold]")
    for tool in TOOLS:
        _run(["uv", "tool", "uninstall", tool], tool)


@app.command("install-skills")
def install_skills() -> None:
    """Copy skill directories to ~/.claude/skills/."""
    root = _repo_root()
    source = root / SKILLS_DIR_NAME
    target = _skills_target()

    if not source.is_dir():
        console.print(f"[red]Skills source not found:[/red] {source}")
        raise typer.Exit(code=1)

    target.mkdir(parents=True, exist_ok=True)

    console.print("[bold]Installing skills...[/bold]")
    for skill_dir in sorted(source.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_name = skill_dir.name
        dest = target / skill_name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(skill_dir, dest)
        console.print(f"  [green]✓[/green] {skill_name} → {dest}")


@app.command("uninstall-skills")
def uninstall_skills() -> None:
    """Remove agentutils skills from ~/.claude/skills/."""
    root = _repo_root()
    source = root / SKILLS_DIR_NAME
    target = _skills_target()

    if not source.is_dir():
        console.print("[yellow]No skills source directory found.[/yellow]")
        return

    console.print("[bold]Uninstalling skills...[/bold]")
    for skill_dir in sorted(source.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_name = skill_dir.name
        dest = target / skill_name
        if dest.exists():
            shutil.rmtree(dest)
            console.print(f"  [green]✓[/green] Removed {skill_name}")
        else:
            console.print(f"  [dim]—[/dim] {skill_name} (not installed)")


@app.command()
def status() -> None:
    """Show installation status of tools and skills."""
    root = _repo_root()
    table = Table(title="agentutils status")
    table.add_column("Component", style="bold")
    table.add_column("Type")
    table.add_column("Status")

    # Check tools
    for tool in TOOLS:
        path = shutil.which(tool)
        if path:
            table.add_row(tool, "tool", f"[green]installed[/green] ({path})")
        else:
            table.add_row(tool, "tool", "[red]not installed[/red]")

    # Check skills
    skills_source = root / SKILLS_DIR_NAME
    skills_target = _skills_target()
    if skills_source.is_dir():
        for skill_dir in sorted(skills_source.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_name = skill_dir.name
            dest = skills_target / skill_name
            if dest.exists():
                table.add_row(skill_name, "skill", "[green]installed[/green]")
            else:
                table.add_row(skill_name, "skill", "[red]not installed[/red]")

    console.print(table)


TOOL_DESCRIPTION = """\
agentutils — Installer for agentutils CLI tools and Claude Code skills.

Commands:
  install          Install all CLI tools globally via `uv tool install`
  uninstall        Uninstall all CLI tools
  install-skills   Copy Claude Code skills to ~/.claude/skills/
  uninstall-skills Remove skills from ~/.claude/skills/
  status           Show what's currently installed

Typical usage:
  agentutils install          # make gitro, lsrelated, markdownpeek available everywhere
  agentutils install-skills   # enable Claude Code skills for the tools
  agentutils status           # check what's installed
"""

TOOL_DESCRIPTION_SHORT = """\
## `agentutils`

Installer for agentutils CLI tools and Claude Code skills. Run `agentutils install`
to make tools globally available, `agentutils install-skills` to enable Claude Code
skills, and `agentutils status` to check installation state.
"""


@app.command("tool-description")
def tool_description() -> None:
    """Print the full tool description for agents."""
    print(TOOL_DESCRIPTION)


@app.command("tool-description-short")
def tool_description_short() -> None:
    """Print the short tool description."""
    print(TOOL_DESCRIPTION_SHORT)


def main() -> None:
    app()
