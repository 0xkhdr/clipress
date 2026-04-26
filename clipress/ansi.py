import re

_ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def has_ansi(text: str) -> bool:
    """
    Fast O(n) check: returns True if any ANSI escape sequence is present.
    Uses simple substring search for the ESC character, which all ANSI
    sequences start with. Short-circuits on first match.
    """
    return '\x1b' in text

def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from a string."""
    return _ANSI_ESCAPE.sub('', text)
