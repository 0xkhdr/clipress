from clipress.metrics import count_tokens, format_report, _count_tokens_heuristic


def test_count_tokens():
    text = "hello world this is a test"
    # Just ensure it works without crashing
    res = count_tokens(text)
    assert res > 0


def test_count_tokens_heuristic_better_than_word_count():
    # Path-heavy output: heuristic should give higher count than word*1.3
    path_output = "/var/www/html/rai/up/clipress"
    word_estimate = int(len(path_output.split()) * 1.3)  # 1 * 1.3 = 1
    heuristic_estimate = _count_tokens_heuristic(path_output)
    assert heuristic_estimate > word_estimate, f"Heuristic should handle paths better: {heuristic_estimate} vs {word_estimate}"
    assert heuristic_estimate > 1, "Path should estimate to multiple tokens"

    # Code/shell output with delimiters
    code_output = "function_name(arg1, arg2): return value"
    word_estimate = int(len(code_output.split()) * 1.3)  # 7 * 1.3 = 9
    heuristic_estimate = _count_tokens_heuristic(code_output)
    # Heuristic should handle delimiters (parentheses, comma) creating more segments
    assert heuristic_estimate > word_estimate / 2, "Heuristic should be more accurate for code"


def test_count_tokens_heuristic_consistency():
    # Same text should always produce same estimate
    text = "git log --oneline -100"
    est1 = _count_tokens_heuristic(text)
    est2 = _count_tokens_heuristic(text)
    assert est1 == est2, "Token estimate should be consistent"

    # Whitespace variations shouldn't change token count significantly
    text_normalized = _count_tokens_heuristic("git  log   --oneline    -100")
    text_extra_spaces = _count_tokens_heuristic("git log --oneline -100")
    assert text_normalized == text_extra_spaces, "Extra spaces shouldn't change token count"


def test_format_report():
    summary = {
        "total_learned": 10,
        "total_tokens_saved": 500,
        "hot_commands": ["git status", "pytest"],
    }
    report = format_report(summary)
    assert "10" in report
    assert "500" in report
    assert "git status" in report
    assert "pytest" in report
