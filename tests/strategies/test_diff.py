from clipress.strategies.diff_strategy import DiffStrategy


def test_diff_strategy_basic():
    strategy = DiffStrategy()
    output = "index 12345\n--- a/file.txt\n+++ b/file.txt\n@@ -1,3 +1,3 @@\n context 1\n context 2\n context 3\n-old\n+new\n context 4\n context 5\n context 6"
    compressed = strategy.compress(output, {"context_lines": 1}, {})
    assert "index " not in compressed
    assert "--- a/file.txt" in compressed
    assert "context 3" in compressed
    assert "context 4" in compressed
    assert "context 1" not in compressed


def test_diff_strategy_too_large():
    strategy = DiffStrategy()
    output = "--- a/file.txt\n+++ b/file.txt\n@@ -1,100 +1,100 @@\n" + "\n".join(
        ["+new line" for _ in range(100)]
    )
    compressed = strategy.compress(output, {"max_lines": 50}, {})
    assert "summarized by file" in compressed
    assert "file.txt: +100 -0" in compressed
