from clipress.strategies.list_strategy import ListStrategy


def test_list_strategy_basic():
    strategy = ListStrategy()
    output = "\n".join([f"item_{i}" for i in range(100)])
    compressed = strategy.compress(
        output, {"max_lines": 30, "head_lines": 20, "tail_lines": 5}, {}
    )
    lines = compressed.splitlines()
    assert len(lines) == 26
    assert "item_0" in lines
    assert "... [75 more items]" in compressed
    assert "item_99" in lines


def test_list_strategy_group_by_dir():
    strategy = ListStrategy()
    output = "src/a.py\nsrc/b.py\nsrc/c.py\nsrc/d.py\nMakefile\n"
    compressed = strategy.compress(output, {"group_by_directory": True}, {})
    assert "src/... [4 files]" in compressed
    assert "Makefile" in compressed


def test_list_strategy_contract():
    strategy = ListStrategy()
    output = "\n".join([f"item_{i}" for i in range(100)])
    contract = {"always_keep": [r"item_50"]}
    compressed = strategy.compress(
        output, {"max_lines": 30, "head_lines": 20, "tail_lines": 5}, contract
    )
    assert "item_50" in compressed


def test_list_strategy_dedup():
    strategy = ListStrategy()
    output = "\n".join(["same_item"] * 50 + ["unique_item"])
    compressed = strategy.compress(output, {"dedup": True}, {})
    assert "repeated 50x" in compressed
    assert "unique_item" in compressed
    # Should not have 50 separate same_item lines
    assert compressed.count("same_item") == 1
