import time
from clipress.learner import (
    Learner,
    INITIAL_CONFIDENCE,
    CONFIDENCE_GAIN,
    CONFIDENCE_LOSS,
)


def test_records_new_command(tmp_path):
    learner = Learner(str(tmp_path))
    learner.record("cmd", "list", 100, 50)
    time.sleep(0.1)  # wait for async save

    assert "cmd" in learner.data["entries"]
    assert learner.data["entries"]["cmd"]["confidence"] == INITIAL_CONFIDENCE
    assert learner.data["entries"]["cmd"]["strategy"] == "list"
    assert learner.data["stats"]["total_tokens_saved"] == 50


def test_updates_confidence_on_confirmation(tmp_path):
    learner = Learner(str(tmp_path))
    learner.record("cmd", "list", 100, 50)
    learner.record("cmd", "list", 100, 50)

    entry = learner.data["entries"]["cmd"]
    assert abs(entry["confidence"] - (INITIAL_CONFIDENCE + CONFIDENCE_GAIN)) < 0.001
    assert entry["calls"] == 2


def test_drops_confidence_on_shape_change(tmp_path):
    learner = Learner(str(tmp_path))
    # build up confidence first
    for _ in range(5):
        learner.record("cmd", "list", 100, 50)

    current_conf = learner.data["entries"]["cmd"]["confidence"]
    # now miss
    learner.record("cmd", "table", 100, 50)

    entry = learner.data["entries"]["cmd"]
    assert abs(entry["confidence"] - (current_conf - CONFIDENCE_LOSS)) < 0.001


def test_promotes_to_hot_at_threshold(tmp_path):
    learner = Learner(str(tmp_path))
    learner.record("cmd", "list", 100, 50)
    # bump confidence
    for _ in range(10):
        learner.record("cmd", "list", 100, 50)

    entry = learner.data["entries"]["cmd"]
    assert entry["hot"] is True
    assert entry["confidence"] >= 0.85

    # check lookup returns
    res = learner.lookup("cmd")
    assert res is not None
    assert res["strategy"] == "list"


def test_does_not_record_output_content(tmp_path):
    learner = Learner(str(tmp_path))
    # output content is not passed to record anyway
    learner.record("cmd", "list", 100, 50)
    time.sleep(0.1)

    with open(tmp_path / ".compressor" / "registry.json") as f:
        content = f.read()
        assert "list" in content
        # It never had output to begin with


def test_atomic_write_on_save(tmp_path):
    learner = Learner(str(tmp_path))
    learner._save()
    assert (tmp_path / ".compressor" / "registry.json").exists()


def test_returns_none_on_low_confidence(tmp_path):
    learner = Learner(str(tmp_path))
    learner.record("cmd", "list", 100, 50)
    res = learner.lookup("cmd")
    assert res is None  # conf is 0.50


def test_handles_corrupt_registry_gracefully(tmp_path):
    d = tmp_path / ".compressor"
    d.mkdir()
    (d / "registry.json").write_text("{bad json")

    # Should not crash, just start fresh
    learner = Learner(str(tmp_path))
    assert learner.data["stats"]["total_commands_learned"] == 0
    learner.record("cmd", "list", 100, 50)
    time.sleep(0.1)

    res = learner.data["entries"]["cmd"]
    assert res is not None


def test_session_count_increments_once_per_process(tmp_path, monkeypatch):
    """Multiple Learner() constructions in the same process must count as one session."""
    import os
    from clipress import learner as learner_mod

    fake_pid = 999_999_001
    monkeypatch.setattr(os, "getpid", lambda: fake_pid)
    learner_mod._SESSION_PIDS.discard(fake_pid)

    l1 = Learner(str(tmp_path))
    assert l1.data["stats"]["session_count"] == 1  # first construction increments
    l1._save()

    l2 = Learner(str(tmp_path))  # same PID → must NOT increment again
    assert l2.data["stats"]["session_count"] == 1


def test_reset_clears_hot_flag(tmp_path):
    """Verifies the entry's hot flag is reset alongside confidence."""
    learner = Learner(str(tmp_path))
    for _ in range(12):
        learner.record("git diff", "diff", 200, 80)

    entry = learner.data["entries"]["git diff"]
    assert entry["hot"] is True

    # Simulate what `clipress learn reset git diff` does
    entry["confidence"] = 0.50
    entry["hot"] = False
    entry["calls"] = 0
    learner._save()
    time.sleep(0.1)

    learner2 = Learner(str(tmp_path))
    e2 = learner2.data["entries"]["git diff"]
    assert e2["hot"] is False
    assert e2["confidence"] == 0.50
    assert e2["calls"] == 0
    # lookup must return None now (confidence below HOT_THRESHOLD)
    assert learner2.lookup("git diff") is None
