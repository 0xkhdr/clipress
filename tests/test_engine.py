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
    d = tmp_path / ".compressor"
    d.mkdir()
    (d / "config.yaml").write_text("""
contracts:
  always_keep:
    - "CRITICAL_LINE"
""")
    output = "line 1\nCRITICAL_LINE\n" + ("line\n" * 50)
    res = compress("ls", output, str(tmp_path))
    assert "CRITICAL_LINE" in res


def test_contract_always_strip_applied_last(tmp_path):
    d = tmp_path / ".compressor"
    d.mkdir()
    (d / "config.yaml").write_text("""
contracts:
  always_strip:
    - "STRIP_ME"
""")
    output = "line 1\nSTRIP_ME\n" + ("line\n" * 50)
    res = compress("ls", output, str(tmp_path))
    assert "STRIP_ME" not in res
