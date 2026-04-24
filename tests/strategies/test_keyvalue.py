from clipress.strategies.keyvalue_strategy import KeyvalueStrategy


def test_keyvalue_strategy_basic():
    strategy = KeyvalueStrategy()
    output = "\n".join([f"Key {i}: Value {i}" for i in range(30)])
    compressed = strategy.compress(output, {"max_lines": 10}, {})
    assert "additional pairs omitted" in compressed
    assert "Key 29" not in compressed


def test_keyvalue_strategy_strip_keys():
    strategy = KeyvalueStrategy()
    output = "Name: App\nSecret: 12345"
    compressed = strategy.compress(output, {"always_strip_keys": ["Secret"]}, {})
    assert "Name: App" in compressed
    assert "Secret: 12345" not in compressed
