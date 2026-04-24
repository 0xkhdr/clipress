from clipress.strategies.test_strategy import TestStrategy


def test_test_strategy_failed_only():
    strategy = TestStrategy()
    output = "test_1.py PASSED\ntest_2.py FAILED\nTraceback...\nAssertionError: x != y\n===== 1 failed, 1 passed ====="
    compressed = strategy.compress(
        output, {"keep": "failed_only", "max_traceback_lines": 8}, {}
    )
    assert "PASSED" not in compressed
    assert "FAILED" in compressed
    assert "AssertionError" in compressed
    assert "1 failed, 1 passed" in compressed


def test_test_strategy_contract():
    strategy = TestStrategy()
    output = "test_1.py PASSED\ntest_2.py FAILED\n===== 1 failed, 1 passed ====="
    contract = {"always_keep": ["test_1.py"]}
    compressed = strategy.compress(output, {}, contract)
    assert "test_1.py PASSED" in compressed
    assert "FAILED" in compressed
