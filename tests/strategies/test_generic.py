from clipress.strategies.generic_strategy import GenericStrategy


def test_generic_strategy_basic():
    strategy = GenericStrategy()
    output = "hello\n" * 10
    compressed = strategy.compress(
        output, {"dedup_min_repeats": 3, "max_lines": 50}, {}
    )
    assert "hello [repeated 10x]" in compressed


def test_generic_strategy_truncate():
    strategy = GenericStrategy()
    output = "\n".join([f"line {i}" for i in range(100)])
    compressed = strategy.compress(
        output, {"max_lines": 10, "head_lines": 5, "tail_lines": 2}, {}
    )
    lines = compressed.splitlines()
    assert len(lines) == 8  # 5 head + 1 omitted marker + 2 tail
    assert "line 0" in compressed
    assert "line 99" in compressed
    assert "more lines" in compressed


def test_generic_strategy_contract():
    strategy = GenericStrategy()
    output = "hello\nworld\nfoo\nbar"
    compressed = strategy.compress(
        output,
        {"max_lines": 2, "head_lines": 1, "tail_lines": 0},
        {"always_keep": ["bar"]},
    )
    assert "hello" in compressed
    assert "bar" in compressed
