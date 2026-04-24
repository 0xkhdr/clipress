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


def test_table_strategy_column_limit():
    """Data rows beyond max_columns should be truncated; header passes through unchanged."""
    import re
    strategy = TableStrategy()
    # Use a separator-based header so header_idx is detected correctly (header + sep)
    header = "A    B    C    D    E    F    G"
    sep = "---  ---  ---  ---  ---  ---  ---"
    rows = "\n".join(f"a{i}   b{i}   c{i}   d{i}   e{i}   f{i}   g{i}" for i in range(5))
    output = f"{header}\n{sep}\n{rows}"
    compressed = strategy.compress(output, {"max_columns": 3, "max_rows": 10}, {})
    lines = compressed.splitlines()
    # Skip header (index 0), separator, and "omitted" lines — only check data rows
    data_rows = [
        ln for ln in lines[2:]
        if ln.strip() and "omitted" not in ln and not re.match(r"^[-\s|+]+$", ln)
    ]
    for line in data_rows:
        cols = [p for p in re.split(r"\s{2,}", line) if p.strip()]
        assert len(cols) <= 3, f"Row has too many columns: {line!r}"


def test_table_strategy_separator_line_preserved():
    """Separator lines (---) should pass through unchanged."""
    strategy = TableStrategy()
    output = "NAME   AGE\n------  ---\nAlice   30\nBob     25"
    compressed = strategy.compress(output, {"max_rows": 20}, {})
    assert "------" in compressed
