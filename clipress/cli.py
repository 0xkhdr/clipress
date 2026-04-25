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

    click.echo("Initialized clipress in this directory.")


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
