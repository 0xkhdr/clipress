import re

_ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from a string."""
    return _ANSI_ESCAPE.sub('', text)
