from clipress.strategies.error_strategy import ErrorStrategy


def test_error_strategy_basic():
    strategy = ErrorStrategy()
    output = 'Traceback (most recent call last):\n  File "a.py", line 1\n    x = 1\n  File "b.py", line 2\n    y = 2\nValueError: bad'
    compressed = strategy.compress(output, {"max_traceback_lines": 1}, {})
    assert "additional frames omitted" in compressed
    assert "ValueError: bad" in compressed
    assert "b.py" not in compressed


def test_error_strategy_strip_stdlib():
    strategy = ErrorStrategy()
    output = 'Traceback:\n  File "/usr/lib/python/x.py", line 1\n    pass\n  File "my_code.py", line 2\n    fail()\nError: x'
    compressed = strategy.compress(output, {"strip_stdlib_frames": True}, {})
    assert "my_code.py" in compressed
    assert "/usr/lib/python" not in compressed
