import sys
import click
import os
import json
from pathlib import Path
from clipress.engine import compress
from clipress.learner import Learner
from clipress.config import get_config
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
    config_path = Path(workspace) / ".compressor" / "config.yaml"

    click.echo(f"Workspace: {workspace}")
    click.echo(f"Config path: {config_path} (Exists: {config_path.exists()})")
    click.echo(format_report(learner.summary()))


@main.command()
def init():
    """Initializes .compressor/ in current directory"""
    workspace = os.getcwd()
    comp_dir = Path(workspace) / ".compressor"
    comp_dir.mkdir(mode=0o700, exist_ok=True)

    config_path = comp_dir / "config.yaml"
    if not config_path.exists():
        # Just write empty defaults for user to override
        config_path.write_text(
            "# clipress workspace configuration\nengine:\n  show_metrics: true\n"
        )
        click.echo("Created .compressor/config.yaml")

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
            learner.data["entries"][command_name]["confidence"] = 0.50
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
    """Validates .compressor/config.yaml against schema"""
    workspace = os.getcwd()
    try:
        get_config(workspace)
        click.echo("Config is valid.")
    except Exception as e:
        click.echo(f"Config is invalid: {e}")


@main.command()
def report():
    """Prints full session report"""
    workspace = os.getcwd()
    learner = Learner(workspace)
    click.echo(format_report(learner.summary()))


if __name__ == "__main__":
    main()
