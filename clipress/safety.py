import re
from pathlib import Path

# Word boundaries prevent false positives like "secretary" or "password_strength_meter".
SECURITY_PATTERNS = [
    r"\.env$",
    r"\.env\.",  # .env files
    r"\bid_rsa\b",
    r"\bid_ed25519\b",  # SSH private keys
    r"\.pem$",
    r"\.key$",  # certificates
    r"\bcredentials\b",  # AWS credentials file
    r"\bsecret\b",  # generic secret
    r"\bpassword\b",  # generic password
    r"\bapi[_-]?key\b",  # API keys
    r"\bAWS_SECRET\b",  # AWS specific
    r"\bGITHUB_TOKEN\b",  # GitHub tokens
    r"\bbearer\s+[a-zA-Z0-9]",  # Bearer tokens in output
    r"-----BEGIN",  # PEM header
]

# Commands that dump environment variables — their output is always security-sensitive
SENSITIVE_ENV_COMMANDS = ["printenv", "declare", "env", "set"]

_DEFAULT_COMPILED = [re.compile(p, re.IGNORECASE) for p in SECURITY_PATTERNS]

# Per-workspace cache of compiled user patterns. Populated from config["safety"]["security_patterns"]
# so users can extend the list without patching source.
_USER_PATTERN_CACHE: dict[int, list[re.Pattern[str]]] = {}


def _compile_user_patterns(patterns: list[str]) -> list[re.Pattern[str]]:
    key = id(patterns)
    cached = _USER_PATTERN_CACHE.get(key)
    if cached is not None:
        return cached
    compiled: list[re.Pattern[str]] = []
    for p in patterns:
        try:
            compiled.append(re.compile(p, re.IGNORECASE))
        except re.error:
            # Invalid regex — skip silently so a single bad pattern doesn't break safety.
            continue
    _USER_PATTERN_CACHE[key] = compiled
    return compiled


def load_blocklist(workspace: str) -> list[str]:
    """
    Reads .clipress/.clipress-ignore.
    Each line is a command prefix (exact match at start of normalized command).
    Empty lines and lines starting with # are ignored.
    """
    ignore_file = Path(workspace) / ".clipress" / ".clipress-ignore"
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


def is_security_sensitive(
    command: str, output: str, extra_patterns: list[re.Pattern[str]] | None = None
) -> bool:
    """
    Returns True if command or output contains security patterns.
    Checks command path AND output content.
    Also blocks environment-dumping commands (printenv, declare, env, set).

    `extra_patterns` are user-supplied compiled regexes (from config) that extend the defaults.
    """
    cmd_base = command.strip().split()[0] if command.strip() else ""
    if cmd_base in SENSITIVE_ENV_COMMANDS:
        return True

    all_patterns = _DEFAULT_COMPILED + (extra_patterns or [])

    # Check command against security patterns
    for p in all_patterns:
        if p.search(command):
            return True

    # Check output content against security patterns
    for p in all_patterns:
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

    user_patterns = config.get("safety", {}).get("security_patterns", []) or []
    extra_compiled = _compile_user_patterns(user_patterns) if user_patterns else None
    if is_security_sensitive(command, output, extra_compiled):
        return True, "security sensitive content detected"

    non_ascii_ratio = config.get("safety", {}).get("binary_non_ascii_ratio", 0.3)
    if is_binary(output, non_ascii_ratio=non_ascii_ratio):
        return True, "binary output detected"

    min_lines = config.get("engine", {}).get("min_lines_to_compress", 15)
    if is_minimal(output, threshold=min_lines):
        return True, "minimal output"

    if config.get("engine", {}).get("pass_through_on_error", True):
        from clipress.classifier import detect
        shape, conf = detect(output)
        if shape == "error" and conf >= 0.7:
            return True, "error output pass-through"

    return False, ""
