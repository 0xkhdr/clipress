import sys
import subprocess
import click
import os
import json
import shutil
import threading
import time
from pathlib import Path
from ruamel.yaml import YAML
from clipress.engine import compress, get_stream_handler
from clipress.learner import Learner
from clipress.config import get_config, validate_config_file, ConfigError, clear_cache
from clipress.metrics import format_report
from clipress.safety import is_security_sensitive, _compile_user_patterns


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

    config_path = comp_dir / "config.yaml"
    if not config_path.exists():
        config_path.write_text(
            "# clipress workspace configuration\n"
            "# See README for full schema.\n"
            "engine:\n"
            "  show_metrics: true\n"
            "#  max_output_bytes: 10485760  # 10 MB\n"
            "#  pass_through_on_error: true\n"
            "#  heartbeat_enabled: true\n"
            "#  heartbeat_interval_seconds: 5\n"
            "#  heartbeat_line_threshold: 500\n"
            "\n"
            "# Per-command output contracts and strategy params\n"
            "# commands:\n"
            "#   \"git log\":\n"
            "#     params:\n"
            "#       max_lines: 50\n"
            "#     always_keep:\n"
            "#       - \"^On branch\"\n"
        )
        click.echo("  Created .clipress/config.yaml")

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

    _register_claude_hook(workspace)
    _register_gemini_hook(workspace)
    click.echo("Initialized clipress in this directory.")


_HOOK_COMMAND = "clipress hook"


def _resolve_hook_command() -> str:
    """Return the hook command with full binary path when clipress is not on PATH."""
    clipress_in_path = shutil.which("clipress")
    if clipress_in_path:
        return f"{clipress_in_path} hook"
    # Venv or editable install: look in the same bin dir as the running Python
    bin_dir = os.path.dirname(sys.executable)
    candidate = os.path.join(bin_dir, "clipress")
    if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
        return f"{candidate} hook"
    return _HOOK_COMMAND


def _write_hook_to_settings(
    settings_path: Path,
    matcher: str,
    label: str,
    event_name: str = "PostToolUse",
    hook_command: str | None = None,
) -> bool:
    """Insert a hook entry into a settings.json file. Returns True if written."""
    cmd = hook_command or _HOOK_COMMAND
    settings: dict = {}
    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            settings = {}

    hooks = settings.setdefault("hooks", {})
    event_hooks: list = hooks.setdefault(event_name, [])

    for h in event_hooks:
        if h.get("matcher") == matcher:
            for sub in h.get("hooks", []):
                existing_cmd = sub.get("command", "")
                if existing_cmd == cmd:
                    return False  # already present with identical command
                if existing_cmd.endswith("clipress hook"):
                    # Upgrade bare "clipress hook" → full resolved path
                    sub["command"] = cmd
                    with open(settings_path, "w", encoding="utf-8") as f:
                        json.dump(settings, f, indent=2)
                    click.echo(f"  Updated {event_name} hook command in {label}")
                    return True

    event_hooks.append({"matcher": matcher, "hooks": [{"type": "command", "command": cmd}]})
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    click.echo(f"  Registered {event_name} hook in {label}")
    return True


def _remove_hook_from_settings(settings_path: Path, matcher: str, label: str, event_name: str = "PostToolUse") -> bool:
    """Remove a hook entry from a settings.json file. Returns True if removed."""
    if not settings_path.exists():
        return False
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
    except Exception:
        return False

    if "hooks" not in settings or event_name not in settings["hooks"]:
        return False

    new_event_hooks = []
    removed = False
    for h in settings["hooks"][event_name]:
        if h.get("matcher") == matcher:
            # Match bare "clipress hook" and full-path ".../clipress hook" forms
            new_subs = [sh for sh in h.get("hooks", []) if not sh.get("command", "").endswith("clipress hook")]
            if len(new_subs) != len(h.get("hooks", [])):
                removed = True
                if new_subs:
                    h["hooks"] = new_subs
                    new_event_hooks.append(h)
            else:
                new_event_hooks.append(h)
        else:
            new_event_hooks.append(h)

    if not removed:
        return False

    settings["hooks"][event_name] = new_event_hooks
    if not settings["hooks"][event_name]:
        del settings["hooks"][event_name]
    if not settings["hooks"]:
        del settings["hooks"]

    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    click.echo(f"  Unregistered {event_name} hook from {label}")
    return True


def _register_claude_hook(workspace: str) -> None:
    """Adds the PostToolUse hook to .claude/settings.json in the project workspace."""
    claude_dir = Path(workspace) / ".claude"
    claude_dir.mkdir(mode=0o700, exist_ok=True)
    settings_path = claude_dir / "settings.json"
    try:
        cmd = _resolve_hook_command()
        _write_hook_to_settings(settings_path, "Bash", ".claude/settings.json", hook_command=cmd)
    except Exception as e:
        click.echo(f"  Warning: Could not register Claude Code hook: {e}")

    # If the global hook still exists, remove it to prevent double compression.
    _remove_global_claude_hook(silent=False)


def _unregister_claude_hook(workspace: str) -> None:
    """Removes the PostToolUse hook from .claude/settings.json in the project workspace."""
    settings_path = Path(workspace) / ".claude" / "settings.json"
    try:
        _remove_hook_from_settings(settings_path, "Bash", ".claude/settings.json")
    except Exception as e:
        click.echo(f"  Warning: Could not unregister Claude Code hook: {e}")


def _remove_global_claude_hook(silent: bool = True) -> None:
    """Removes the PostToolUse hook from the global ~/.claude/settings.json if present."""
    global_path = Path.home() / ".claude" / "settings.json"
    try:
        removed = _remove_hook_from_settings(global_path, "Bash", "~/.claude/settings.json (global)")
        if removed and not silent:
            click.echo("  Note: Removed global hook to prevent double compression.")
    except Exception:
        pass


def _register_gemini_hook(workspace: str) -> None:
    """Adds the AfterTool hook to .gemini/settings.json in the project workspace."""
    gemini_dir = Path(workspace) / ".gemini"
    gemini_dir.mkdir(mode=0o700, exist_ok=True)
    settings_path = gemini_dir / "settings.json"
    try:
        cmd = _resolve_hook_command()
        # Remove stale "PostToolUse" key written by older versions of clipress.
        _remove_hook_from_settings(settings_path, "run_shell_command", ".gemini/settings.json", event_name="PostToolUse")
        _write_hook_to_settings(settings_path, "run_shell_command", ".gemini/settings.json", event_name="AfterTool", hook_command=cmd)
    except Exception as e:
        click.echo(f"  Warning: Could not register Gemini CLI hook: {e}")


def _unregister_gemini_hook(workspace: str) -> None:
    """Removes the AfterTool hook from .gemini/settings.json in the project workspace."""
    settings_path = Path(workspace) / ".gemini" / "settings.json"
    try:
        _remove_hook_from_settings(settings_path, "run_shell_command", ".gemini/settings.json", event_name="AfterTool")
        # Also clean up stale "PostToolUse" key if present from older versions.
        _remove_hook_from_settings(settings_path, "run_shell_command", ".gemini/settings.json", event_name="PostToolUse")
    except Exception as e:
        click.echo(f"  Warning: Could not unregister Gemini CLI hook: {e}")


@main.group()
def learn():
    """Learned command registry commands"""
    pass


@learn.command()
def show():
    """Displays learned registry in human-readable format"""
    workspace = os.getcwd()
    learner = Learner(workspace)
    click.echo(json.dumps(learner.all_entries(), indent=2))


@learn.command()
@click.argument("command_name", required=False)
def reset(command_name):
    """Resets confidence for a specific command or all"""
    workspace = os.getcwd()
    learner = Learner(workspace)
    if command_name:
        if learner.reset_command(command_name):
            click.echo(f"Reset {command_name}")
        else:
            click.echo(f"Command not found: {command_name}")
    else:
        learner.reset_all()
        click.echo("Reset all learned commands")


@main.command(name="compress")
@click.argument("cmd_string")
@click.option("--workspace", default=None)
def compress_cmd(cmd_string, workspace):
    """Compresses stdin output based on command string"""
    if not workspace:
        workspace = os.getcwd()

    # Read heartbeat config before draining stdin so the interval is correct.
    cfg_engine = get_config(workspace).get("engine", {})
    hb_enabled = cfg_engine.get("heartbeat_enabled", True)
    hb_interval = float(cfg_engine.get("heartbeat_interval_seconds", 5))

    hb_stop: threading.Event | None = None
    hb_thread: threading.Thread | None = None

    if hb_enabled:
        hb_stop = threading.Event()
        hb_start_time = time.monotonic()

        def _heartbeat():
            while not hb_stop.wait(hb_interval):  # type: ignore[union-attr]
                elapsed = time.monotonic() - hb_start_time
                print(
                    f"[clipress: reading output (elapsed {elapsed:.0f}s)]",
                    file=sys.stderr,
                )

        hb_thread = threading.Thread(target=_heartbeat, daemon=True)
        hb_thread.start()

    try:
        output = sys.stdin.read()
    finally:
        if hb_stop is not None:
            hb_stop.set()
        if hb_thread is not None:
            hb_thread.join(timeout=1.0)

    res = compress(cmd_string, output, workspace)
    click.echo(res, nl=False)


@main.command(name="run", context_settings=dict(allow_interspersed_args=False, ignore_unknown_options=True))
@click.argument("command", nargs=-1, required=True, type=click.UNPROCESSED)
@click.option("--workspace", default=None)
@click.option(
    "--stall-timeout",
    default=2.0,
    type=float,
    show_default=True,
    help="Seconds without output before assuming an interactive prompt.",
)
def run_cmd(command, workspace, stall_timeout):
    """Run a command with PTY support; auto-switches to raw passthrough on interactive prompts.

    Unlike piping into 'clipress compress', this subcommand spawns the process
    inside a pseudo-terminal so programs that require a TTY work correctly.
    When output stalls (no data for --stall-timeout seconds) and the child is
    still alive, clipress compresses what it has buffered, then hands control
    back to the terminal so you can respond to the interactive prompt.

    For commands marked streamable in the seed registry (docker build, npm install,
    cargo build, etc.) output is filtered and emitted in real time rather than
    buffered until the process exits.

    Example:
        clipress run docker build -t myapp .
        clipress run python manage.py shell
    """
    try:
        import pty
        import select
        import termios
        import tty
    except ImportError:
        click.echo(
            "clipress run: PTY support requires Unix (pty/termios modules). "
            "Use piping on this platform: cmd | clipress compress 'cmd'",
            err=True,
        )
        sys.exit(1)

    if not workspace:
        workspace = os.getcwd()

    cmd_list = list(command)
    cmd_str = " ".join(cmd_list)

    # Check for streaming path before spawning the process
    stream_handler = get_stream_handler(cmd_str, workspace)

    master_fd, slave_fd = pty.openpty()

    try:
        proc = subprocess.Popen(
            cmd_list,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
        )
    except FileNotFoundError:
        os.close(master_fd)
        os.close(slave_fd)
        click.echo(f"clipress run: command not found: {cmd_list[0]}", err=True)
        sys.exit(127)
    except Exception as e:
        os.close(master_fd)
        os.close(slave_fd)
        click.echo(f"clipress run: failed to start '{cmd_str}': {e}", err=True)
        sys.exit(1)

    os.close(slave_fd)

    try:
        if stream_handler is not None:
            _run_streaming(master_fd, proc, cmd_str, workspace, stall_timeout, stream_handler, select, termios, tty)
        else:
            _run_buffered(master_fd, proc, cmd_str, workspace, stall_timeout, select, termios, tty)
    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass

    proc.wait()
    sys.exit(proc.returncode or 0)


def _run_buffered(
    master_fd: int,
    proc: subprocess.Popen,
    cmd_str: str,
    workspace: str,
    stall_timeout: float,
    select,
    termios,
    tty,
) -> None:
    """Buffer all PTY output, then compress and emit in one pass."""
    import select as _select

    output_chunks: list[str] = []
    switched_to_passthrough = False

    while True:
        if proc.poll() is not None:
            while True:
                r, _, _ = _select.select([master_fd], [], [], 0.05)
                if not r:
                    break
                try:
                    chunk = os.read(master_fd, 4096)
                    if chunk:
                        output_chunks.append(chunk.decode("utf-8", errors="replace"))
                except OSError:
                    break
            break

        r, _, _ = _select.select([master_fd], [], [], stall_timeout)

        if not r:
            # Stall detected — child is alive but emitting nothing
            if output_chunks:
                buffered = "".join(output_chunks)
                result = compress(cmd_str, buffered, workspace)
                sys.stdout.write(result)
                if result and not result.endswith("\n"):
                    sys.stdout.write("\n")
                sys.stdout.flush()
                output_chunks.clear()

            click.echo(
                "[clipress: interactive prompt detected — switching to passthrough]",
                err=True,
            )
            switched_to_passthrough = True
            _run_passthrough(master_fd, proc, stall_timeout, termios, tty)
            break

        try:
            chunk = os.read(master_fd, 4096)
            if not chunk:
                break
            output_chunks.append(chunk.decode("utf-8", errors="replace"))
        except OSError:
            break

    if not switched_to_passthrough and output_chunks:
        buffered = "".join(output_chunks)
        result = compress(cmd_str, buffered, workspace)
        sys.stdout.write(result)
        if result and not result.endswith("\n"):
            sys.stdout.write("\n")
        sys.stdout.flush()


def _run_streaming(
    master_fd: int,
    proc: subprocess.Popen,
    cmd_str: str,
    workspace: str,
    stall_timeout: float,
    stream_handler,
    select,
    termios,
    tty,
) -> None:
    """
    Streaming path for known-streamable commands (Phase 2).

    Lines are filtered by the StreamStrategy as they arrive:
    - Progress spam is swallowed
    - Error lines are emitted immediately
    - The final significant line is held and emitted at finalize()

    Safety: each line is checked against security patterns before emission.
    """
    import select as _select

    strategy, _params = stream_handler
    config = get_config(workspace)
    user_patterns_raw = config.get("safety", {}).get("security_patterns", []) or []
    extra_compiled = _compile_user_patterns(user_patterns_raw) if user_patterns_raw else None

    line_buf = ""  # Accumulates partial lines from PTY chunks

    def _safe_emit(line: str) -> None:
        """Emit a line after security check."""
        # Strip ANSI if configured
        from clipress.ansi import strip_ansi as _strip
        if config.get("engine", {}).get("strip_ansi", True):
            line = _strip(line)
        if not line.strip():
            return
        if is_security_sensitive("", line, extra_compiled):
            return  # Silently drop sensitive content
        sys.stdout.write(line + "\n")
        sys.stdout.flush()

    def _process_line_buf(buf: str) -> str:
        """Split buf on newlines, process complete lines, return remainder."""
        *complete, remainder = buf.split("\n")
        for ln in complete:
            result = strategy.process_line(ln)
            if result is not None:
                _safe_emit(result)
        return remainder

    while True:
        if proc.poll() is not None:
            # Drain remaining output
            while True:
                r, _, _ = _select.select([master_fd], [], [], 0.05)
                if not r:
                    break
                try:
                    chunk = os.read(master_fd, 4096)
                    if chunk:
                        line_buf += chunk.decode("utf-8", errors="replace")
                        line_buf = _process_line_buf(line_buf)
                except OSError:
                    break
            break

        r, _, _ = _select.select([master_fd], [], [], stall_timeout)

        if not r:
            # Stall: could be an interactive prompt — switch to passthrough
            click.echo(
                "[clipress: interactive prompt detected — switching to passthrough]",
                err=True,
            )
            # Flush remaining buffered line
            if line_buf.strip():
                result = strategy.process_line(line_buf)
                if result is not None:
                    _safe_emit(result)
                line_buf = ""
            # Emit finalize lines before handing off
            for fin_line in strategy.finalize():
                _safe_emit(fin_line)
            _run_passthrough(master_fd, proc, stall_timeout, termios, tty)
            return

        try:
            chunk = os.read(master_fd, 4096)
            if not chunk:
                break
            line_buf += chunk.decode("utf-8", errors="replace")
            line_buf = _process_line_buf(line_buf)
        except OSError:
            break

    # Process any leftover partial line
    if line_buf.strip():
        result = strategy.process_line(line_buf)
        if result is not None:
            _safe_emit(result)

    # Emit final lines (e.g. captured "final status" line)
    for fin_line in strategy.finalize():
        _safe_emit(fin_line)


def _run_passthrough(master_fd: int, proc: subprocess.Popen, timeout: float, termios, tty) -> None:
    """Bidirectional raw passthrough: stdin → PTY slave, PTY master → stdout."""
    import select

    old_settings = None
    stdin_fd = sys.stdin.fileno() if sys.stdin.isatty() else None

    if stdin_fd is not None:
        try:
            old_settings = termios.tcgetattr(stdin_fd)
            tty.setraw(stdin_fd)
        except Exception:
            stdin_fd = None

    try:
        while proc.poll() is None:
            watch = [master_fd]
            if stdin_fd is not None:
                watch.append(stdin_fd)

            r, _, _ = select.select(watch, [], [], timeout)

            for fd in r:
                if fd == master_fd:
                    try:
                        data = os.read(master_fd, 4096)
                        if data:
                            sys.stdout.buffer.write(data)
                            sys.stdout.buffer.flush()
                    except OSError:
                        return
                elif fd == stdin_fd:
                    try:
                        data = os.read(stdin_fd, 4096)
                        if data:
                            os.write(master_fd, data)
                    except OSError:
                        return
    finally:
        if old_settings is not None:
            try:
                termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)
            except Exception:
                pass


@main.command(name="hook", hidden=True)
def hook_cmd():
    """PostToolUse/AfterTool hook entrypoint — reads JSON from stdin, writes JSON to stdout."""
    from clipress.hooks.post_tool_use import main as _hook_main
    _hook_main()


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

    yaml = YAML()
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

    _unregister_claude_hook(workspace)
    _unregister_gemini_hook(workspace)
    _remove_global_claude_hook(silent=False)

    if not keep_data and comp_dir.exists():
        shutil.rmtree(comp_dir)
        click.echo(f"Removed {comp_dir}")

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
