import time
from clipress.engine import compress


def test_engine_returns_original_on_exception(monkeypatch):
    def mock_detect(*args, **kwargs):
        raise Exception("Mock crash")

    monkeypatch.setattr("clipress.engine.detect", mock_detect)

    output = "test output\n" * 20
    res = compress("unknown_command", output, "/tmp")
    assert res == output  # fallback on crash


def test_never_returns_empty_for_nonempty_input():
    output = "some valid output\n" * 20
    res = compress("some_cmd", output, "/tmp")
    assert res != ""
    assert len(res) > 0


def test_safety_gate_runs_before_compression(capsys):
    output = "DATABASE_URL=postgres://user:P4ssw0rd@host/db\n" * 20
    res = compress("cat .env", output, "/tmp")
    assert res == output

    captured = capsys.readouterr()
    assert "clipress: skipped [security sensitive content detected]" in captured.err


def test_contract_always_keep_survives_compression(tmp_path):
    # Configure workspace contract
    d = tmp_path / ".clipress"
    d.mkdir()
    (d / "config.yaml").write_text("""
contracts:
  global:
    always_keep:
      - "CRITICAL_LINE"
""")
    output = "line 1\nCRITICAL_LINE\n" + ("line\n" * 50)
    res = compress("ls", output, str(tmp_path))
    assert "CRITICAL_LINE" in res


def test_contract_always_strip_applied_last(tmp_path):
    d = tmp_path / ".clipress"
    d.mkdir()
    (d / "config.yaml").write_text("""
contracts:
  global:
    always_strip:
      - "STRIP_ME"
""")
    output = "line 1\nSTRIP_ME\n" + ("line\n" * 50)
    res = compress("ls", output, str(tmp_path))
    assert "STRIP_ME" not in res

def test_global_ansi_stripping(tmp_path):
    d = tmp_path / ".clipress"
    d.mkdir()
    (d / "config.yaml").write_text("""
engine:
  strip_ansi: true
""")
    output = "\x1b[31mRed text\x1b[0m\n" * 50
    res = compress("ls", output, str(tmp_path))
    assert "\x1b[31m" not in res

def test_hot_path_under_10ms(tmp_path):
    # Warm up cache
    output = "line\n" * 1000
    compress("ls", output, str(tmp_path))
    compress("ls", output, str(tmp_path))
    
    # Measure
    start = time.time()
    compress("ls", output, str(tmp_path))
    duration = time.time() - start
    
    # Target < 10ms (0.01s)
    # Using 0.05s as safety margin for CI environments, but typically < 0.01s
    assert duration < 0.05


def test_max_output_bytes_passthrough(tmp_path, capsys):
    """GAP-1: Outputs exceeding max_output_bytes must be passed through, not processed."""
    d = tmp_path / ".clipress"
    d.mkdir()
    (d / "config.yaml").write_text("engine:\n  max_output_bytes: 100\n")
    from clipress.config import clear_cache
    clear_cache()

    output = "x" * 200  # 200 bytes > 100 limit
    res = compress("cat big_file", output, str(tmp_path))
    assert res == output
    captured = capsys.readouterr()
    assert "max_output_bytes" in captured.err
    clear_cache()


def test_size_regression_guard(tmp_path):
    """Engine must return the original if compressed output is larger than original."""
    from clipress.strategies.base import BaseStrategy
    from clipress.strategies import STRATEGIES

    class GrowingStrategy(BaseStrategy):
        def compress(self, output, params, contract):
            return output + "\n" * 1000  # deliberately inflate output

    original_strategies = STRATEGIES.copy()
    STRATEGIES["list"] = GrowingStrategy()

    output = "line\n" * 30  # > 15 lines, triggers compression
    res = compress("ls", output, str(tmp_path))
    assert len(res) <= len(output) + 1  # must not have grown

    STRATEGIES.update(original_strategies)  # restore


def test_size_regression_guard_whitespace_bloat(tmp_path):
    """A strategy that adds only whitespace still trips the byte-length guard."""
    from clipress.strategies.base import BaseStrategy
    from clipress.strategies import STRATEGIES

    class WhitespaceBloatStrategy(BaseStrategy):
        def compress(self, output, params, contract):
            return output + "\n" * 5000  # pure whitespace inflation

    original = STRATEGIES.copy()
    STRATEGIES["list"] = WhitespaceBloatStrategy()
    try:
        output = "line\n" * 30
        res = compress("ls", output, str(tmp_path))
        assert len(res) == len(output), (
            f"whitespace bloat leaked through: {len(res)} > {len(output)}"
        )
    finally:
        STRATEGIES.clear()
        STRATEGIES.update(original)


def test_learner_instantiated_once_per_compress(tmp_path, monkeypatch):
    """Learner must be instantiated only once per compress() call, not twice."""
    call_count = [0]
    original_init = __import__('clipress.learner', fromlist=['Learner']).Learner.__init__

    def counting_init(self, workspace):
        call_count[0] += 1
        original_init(self, workspace)

    monkeypatch.setattr(
        "clipress.learner.Learner.__init__", counting_init
    )
    output = "line\n" * 30
    compress("unknown_tool_xyz", output, str(tmp_path))
    assert call_count[0] == 1, f"Expected 1 Learner instantiation, got {call_count[0]}"
