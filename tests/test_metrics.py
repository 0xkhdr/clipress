from clipress.metrics import count_tokens, format_report


def test_count_tokens():
    text = "hello world this is a test"
    # Just ensure it works without crashing
    res = count_tokens(text)
    assert res > 0


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
