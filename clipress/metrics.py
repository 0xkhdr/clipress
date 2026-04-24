def count_tokens(text: str) -> int:
    """
    Approximates token count without tiktoken dependency.
    Uses word-based heuristic: tokens ≈ words * 1.3
    Fast, dependency-free, accurate enough for reporting.

    If tiktoken is installed: use cl100k_base encoding.
    If not installed: use word heuristic.
    tiktoken is OPTIONAL, never a hard dependency.
    """
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        words = len(text.split())
        return int(words * 1.3)


def format_report(summary: dict) -> str:
    total_learned = summary.get("total_learned", 0)
    total_tokens_saved = summary.get("total_tokens_saved", 0)
    hot_commands = summary.get("hot_commands", [])

    lines = [
        "clipress session report",
        "───────────────────────────────────────────",
        f"commands learned : {total_learned}",
        f"tokens saved     : {total_tokens_saved}",
        f"hot commands     : {len(hot_commands)}",
    ]
    if hot_commands:
        lines.append("\nhot commands list:")
        for cmd in hot_commands:
            lines.append(f"  🔥 {cmd}")
    lines.append("───────────────────────────────────────────")
    return "\n".join(lines)
