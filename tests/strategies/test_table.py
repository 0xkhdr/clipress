from clipress.strategies.table_strategy import TableStrategy


def test_table_strategy_basic():
    strategy = TableStrategy()
    output = "ID   NAME   STATUS\n" + "\n".join(
        [f"{i}    obj{i}   RUNNING" for i in range(30)]
    )
    compressed = strategy.compress(output, {"max_rows": 10}, {})
    assert "ID   NAME" in compressed
    assert "0    obj0" in compressed
    assert "additional rows omitted" in compressed
    assert "29   obj29" not in compressed


def test_table_strategy_cell_trunc():
    strategy = TableStrategy()
    output = "ID   DESCRIPTION\n1    " + ("A" * 60)
    compressed = strategy.compress(output, {"max_cell_length": 10}, {})
    assert "A" * 7 + "..." in compressed
    assert "A" * 60 not in compressed
