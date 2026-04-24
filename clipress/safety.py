import re
import os
from pathlib import Path

SECURITY_PATTERNS = [
    r"\.env$",
    r"\.env\.",  # .env files
    r"id_rsa",
    r"id_ed25519",  # SSH private keys
    r"\.pem$",
    r"\.key$",  # certificates
    r"credentials",  # AWS credentials file
    r"secret",  # generic secret
    r"password",  # generic password
    r"api[_-]?key",  # API keys
    r"AWS_SECRET",  # AWS specific
    r"GITHUB_TOKEN",  # GitHub tokens
    r"bearer\s+[a-zA-Z0-9]",  # Bearer tokens in output
    r"-----BEGIN",  # PEM header
]

# Commands that dump environment variables — their output is always security-sensitive
SENSITIVE_ENV_COMMANDS = ["printenv", "declare", "env", "set"]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SECURITY_PATTERNS]


def load_blocklist(workspace: str) -> list[str]:
    """
    Reads .compressor/.compressor-ignore.
    Each line is a command prefix (exact match at start of normalized command).
    Empty lines and lines starting with # are ignored.
    """
    ignore_file = Path(workspace) / ".compressor" / ".compressor-ignore"
    if not ignore_file.exists():
        return []

    blocklist = []
    try:
        with open(ignore_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    blocklist.append(line)
    except Exception:
        pass
    return blocklist


def is_security_sensitive(command: str, output: str) -> bool:
    """
    Returns True if command or output contains security patterns.
    Checks command path AND output content.
    Also blocks environment-dumping commands (printenv, declare, env, set).
    """
    # Block environment-dumping commands unconditionally
    cmd_base = command.strip().split()[0] if command.strip() else ""
    if cmd_base in SENSITIVE_ENV_COMMANDS:
        return True

    # Check command against security patterns
    for p in _COMPILED_PATTERNS:
        if p.search(command):
            return True

    # Check output content against security patterns
    for p in _COMPILED_PATTERNS:
        if p.search(output):
            return True

    return False


def is_binary(output: str, non_ascii_ratio: float = 0.3) -> bool:
    """
    Returns True if output contains binary/non-printable bytes.
    Uses null byte detection + high non-ASCII ratio heuristic.
    Scans the first 4096 bytes for thorough coverage.
    """
    # Check first 4096 chars/bytes (extended from 512 for better coverage)
    sample = output[:4096]
    if "\x00" in sample:
        return True

    # Check non-printable ratio
    printable = sum(1 for c in sample if c.isprintable() or c in "\n\r\t")
    if len(sample) > 0 and (len(sample) - printable) / len(sample) > non_ascii_ratio:
        return True

    return False


def is_minimal(output: str, threshold: int = 15) -> bool:
    """
    Returns True if output line count is below threshold.
    Nothing to compress — pass through.
    """
    lines = output.splitlines()
    return len(lines) < threshold


def should_skip(command: str, output: str, workspace: str, config: dict) -> tuple[bool, str]:
    """
    Returns (should_skip: bool, reason: str)

    reason is empty string if should_skip is False.
    reason is used for stderr warning only, never written to stdout.
    """
    blocklist = load_blocklist(workspace)
    cmd_normalized = command.strip()
    for prefix in blocklist:
        if cmd_normalized.startswith(prefix):
            return True, "command in user blocklist"

    if is_security_sensitive(command, output):
        return True, "security sensitive content detected"

    non_ascii_ratio = config.get("safety", {}).get("binary_non_ascii_ratio", 0.3)
    if is_binary(output, non_ascii_ratio=non_ascii_ratio):
        return True, "binary output detected"

    min_lines = config.get("engine", {}).get("min_lines_to_compress", 15)
    if is_minimal(output, threshold=min_lines):
        return True, "minimal output"

    if config.get("engine", {}).get("pass_through_on_error", False):
        from clipress.classifier import detect
        shape, conf = detect(output)
        if shape == "error" and conf >= 0.7:
            return True, "error output pass-through"

    return False, ""
