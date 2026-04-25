import sys
import subprocess
import click
import os
import json
import shutil
from pathlib import Path
from ruamel.yaml import YAML
from clipress.engine import compress
from clipress.learner import Learner
from clipress.config import get_config, validate_config_file, ConfigError, clear_cache
from clipress.metrics import format_report


@click.group()
def main():
    """Universal CLI output compressor for AI agents"""
    pass


@main.command()
def status():
    """Shows current session stats, learned commands, config path"""
    workspace = os.getcwd()
    learner = Learner(workspace)
    config_path = Path(workspace) / ".clipress" / "config.yaml"

    click.echo(f"Workspace: {workspace}")
    if config_path.exists():
        click.echo(f"Config path: {config_path}")
    else:
        click.echo(f"Config path: {config_path} (not found — run 'clipress init' to set up)")
    click.echo(format_report(learner.summary()))


@main.command()
def init():
    """Initializes .clipress/ in current directory with a full scaffold"""
    workspace = os.getcwd()
    comp_dir = Path(workspace) / ".clipress"
    comp_dir.mkdir(mode=0o700, exist_ok=True)

    # Create config.yaml with commented examples
    config_path = comp_dir / "config.yaml"
    if not config_path.exists():
        config_path.write_text(
            "# clipress workspace configuration\n"
            "# See README for full schema.\n"
            "engine:\n"
            "  show_metrics: true\n"
            "#  max_output_bytes: 10485760  # 10 MB\n"
            "#  pass_through_on_error: true\n"
            "\n"
            "# Per-command output contracts\n"
            "# commands:\n"
            "#   \"git status\":\n"
            "#     always_keep:\n"
            "#       - \"^On branch\"\n"
        )
        click.echo("  Created .clipress/config.yaml")

    # Create extensions directory for custom seed rules
    ext_dir = comp_dir / "extensions"
    ext_dir.mkdir(exist_ok=True)
    example_ext = ext_dir / "example.yaml.disabled"
    if not example_ext.exists():
        example_ext.write_text(
            "# Rename to .yaml to activate. User extensions override built-in seeds.\n"
            "# Format: command_prefix:\n"
            "#   strategy: list|diff|test|progress|table|keyvalue|error|generic\n"
            "#   params:\n"
            "#     max_lines: 30\n"
            "\n"
            "# Example:\n"
            "# \"kubectl get pods\":\n"
            "#   strategy: table\n"
            "#   params:\n"
            "#     max_rows: 20\n"
        )
        click.echo("  Created .clipress/extensions/example.yaml.disabled")

    # Create .clipress-ignore with examples
    ignore_path = comp_dir / ".clipress-ignore"
    if not ignore_path.exists():
        ignore_path.write_text(
            "# Commands listed here are passed through without compression.\n"
            "# One command prefix per line. Lines starting with # are comments.\n"
            "#\n"
            "# Examples:\n"
            "# kubectl exec\n"
            "# psql\n"
            "# mysql\n"
        )
        click.echo("  Created .clipress/.clipress-ignore")

    _register_claude_hook()
    click.echo("Initialized clipress in this directory.")


def _register_claude_hook():
    """Adds the PostToolUse hook to ~/.claude/settings.json if it exists."""
    settings_path = Path.home() / ".claude" / "settings.json"
    if not settings_path.parent.exists():
        # Claude Code doesn't seem to be installed (no ~/.claude folder)
        return

    try:
        settings = {}
        if settings_path.exists():
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)

        hooks = settings.get("hooks", {})
        post_tool_use = hooks.get("PostToolUse", [])

        command = "python -m clipress.hooks.post_tool_use"
        
        # Check if already exists
        exists = False
        for h in post_tool_use:
            if h.get("matcher") == "Bash":
                for sub_hook in h.get("hooks", []):
                    if sub_hook.get("command") == command:
                        exists = True
                        break
            if exists:
                break

        if not exists:
            post_tool_use.append({
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": command}]
            })
            hooks["PostToolUse"] = post_tool_use
            settings["hooks"] = hooks

            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
            click.echo("  Registered PostToolUse hook in ~/.claude/settings.json")
    except Exception as e:
        click.echo(f"  Warning: Could not register Claude hook: {e}")


def _unregister_claude_hook():
    """Removes the PostToolUse hook from ~/.claude/settings.json."""
    settings_path = Path.home() / ".claude" / "settings.json"
    if not settings_path.exists():
        return

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)

        if "hooks" not in settings or "PostToolUse" not in settings["hooks"]:
            return

        post_tool_use = settings["hooks"]["PostToolUse"]
        command = "python -m clipress.hooks.post_tool_use"

        new_post_tool_use = []
        removed = False
        for h in post_tool_use:
            if h.get("matcher") == "Bash":
                sub_hooks = h.get("hooks", [])
                new_sub_hooks = [sh for sh in sub_hooks if sh.get("command") != command]
                if len(new_sub_hooks) != len(sub_hooks):
                    removed = True
                    if new_sub_hooks:
                        h["hooks"] = new_sub_hooks
                        new_post_tool_use.append(h)
                else:
                    new_post_tool_use.append(h)
            else:
                new_post_tool_use.append(h)

        if removed:
            settings["hooks"]["PostToolUse"] = new_post_tool_use
            if not settings["hooks"]["PostToolUse"]:
                del settings["hooks"]["PostToolUse"]
            if not settings["hooks"]:
                del settings["hooks"]

            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
            click.echo("  Unregistered PostToolUse hook from ~/.claude/settings.json")
    except Exception as e:
        click.echo(f"  Warning: Could not unregister Claude hook: {e}")


@main.group()
def learn():
    """Learned command registry commands"""
    pass


@learn.command()
def show():
    """Displays learned.json in human-readable format"""
    workspace = os.getcwd()
    learner = Learner(workspace)
    click.echo(json.dumps(learner.data["entries"], indent=2))


@learn.command()
@click.argument("command_name", required=False)
def reset(command_name):
    """Resets confidence for a specific command or all"""
    workspace = os.getcwd()
    learner = Learner(workspace)
    if command_name:
        if command_name in learner.data["entries"]:
            entry = learner.data["entries"][command_name]
            entry["confidence"] = 0.50
            entry["hot"] = False
            entry["calls"] = 0
            learner._save()
            click.echo(f"Reset {command_name}")
        else:
            click.echo(f"Command not found: {command_name}")
    else:
        learner.data["entries"].clear()
        learner._save()
        click.echo("Reset all learned commands")


@main.command(name="compress")
@click.argument("cmd_string")
@click.option("--workspace", default=None)
def compress_cmd(cmd_string, workspace):
    """Compresses stdin output based on command string"""
    if not workspace:
        workspace = os.getcwd()
    output = sys.stdin.read()
    res = compress(cmd_string, output, workspace)
    click.echo(res, nl=False)


@main.command()
def validate():
    """Validates .clipress/config.yaml against schema"""
    workspace = os.getcwd()
    try:
        validate_config_file(workspace)
        click.echo("Config is valid.")
    except ConfigError as e:
        click.echo(f"Config is invalid: {e}", err=False)
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"Config error: {e}", err=False)
        raise SystemExit(1)


@main.command()
def report():
    """Prints full session report"""
    workspace = os.getcwd()
    learner = Learner(workspace)
    click.echo(format_report(learner.summary()))


@main.command(name="error-passthrough")
@click.argument("state", type=click.Choice(["on", "off"]))
def error_passthrough(state):
    """Toggles error pass-through for the current workspace"""
    workspace = os.getcwd()
    comp_dir = Path(workspace) / ".clipress"
    comp_dir.mkdir(mode=0o700, exist_ok=True)
    config_path = comp_dir / "config.yaml"
    
    yaml = YAML()  # round-trip writer preserves comments
    config = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.load(f) or {}

    if "engine" not in config:
        config["engine"] = {}

    config["engine"]["pass_through_on_error"] = (state == "on")

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f)

    clear_cache()

    click.echo(f"Set pass_through_on_error to {state == 'on'} in {config_path}")


@main.command()
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--keep-data", is_flag=True, help="Keep .clipress/ workspace data")
def uninstall(yes, keep_data):
    """Removes .clipress/ workspace data and uninstalls the clipress package"""
    workspace = os.getcwd()
    comp_dir = Path(workspace) / ".clipress"

    if not yes:
        msg = "This will uninstall clipress"
        if comp_dir.exists() and not keep_data:
            msg += f" and delete {comp_dir}"
        click.confirm(f"{msg}. Continue?", abort=True)

    if not keep_data and comp_dir.exists():
        shutil.rmtree(comp_dir)
        click.echo(f"Removed {comp_dir}")

    _unregister_claude_hook()

    # Try pipx first, fall back to pip
    if shutil.which("pipx"):
        result = subprocess.run(["pipx", "uninstall", "clipress"], capture_output=True, text=True)
        if result.returncode == 0:
            click.echo(result.stdout.strip() or "Uninstalled clipress via pipx.")
            return
        click.echo(result.stderr.strip(), err=True)
    elif shutil.which("pip"):
        result = subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "-y", "clipress"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            click.echo(result.stdout.strip() or "Uninstalled clipress via pip.")
            return
        click.echo(result.stderr.strip(), err=True)
    else:
        click.echo("Could not find pipx or pip — remove clipress manually.", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
