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
    """Verify output content is never persisted — only strategy metadata goes to the DB."""
    learner = Learner(str(tmp_path))
    learner.record("cmd", "list", 100, 50)

    # The SQLite DB must exist and contain strategy name, not raw output
    db_path = tmp_path / ".clipress" / "registry.db"
    assert db_path.exists()

    import sqlite3
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT strategy FROM entries WHERE command='cmd'").fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "list"


def test_registry_uses_sqlite(tmp_path):
    """Verify the registry uses SQLite (registry.db), not JSON."""
    learner = Learner(str(tmp_path))
    learner.record("cmd", "list", 100, 50)

    assert (tmp_path / ".clipress" / "registry.db").exists()


def test_returns_none_on_low_confidence(tmp_path):
    learner = Learner(str(tmp_path))
    learner.record("cmd", "list", 100, 50)
    res = learner.lookup("cmd")
    assert res is None  # conf is 0.50


def test_handles_corrupt_registry_gracefully(tmp_path):
    """A corrupt registry.json (legacy) must not crash Learner init; SQLite starts fresh."""
    d = tmp_path / ".clipress"
    d.mkdir()
    # Write corrupt JSON (legacy format) — migration will fail silently
    (d / "registry.json").write_text("{bad json")

    learner = Learner(str(tmp_path))
    # DB is clean: no entries migrated from corrupt JSON
    assert learner.data["stats"]["total_commands_learned"] == 0
    learner.record("cmd", "list", 100, 50)

    res = learner.data["entries"]["cmd"]
    assert res is not None


def test_reset_clears_hot_flag(tmp_path):
    """Verifies the entry's hot flag is reset alongside confidence."""
    learner = Learner(str(tmp_path))
    for _ in range(12):
        learner.record("git diff", "diff", 200, 80)

    entry = learner.data["entries"]["git diff"]
    assert entry["hot"] is True

    # Use the proper reset API (not dict mutation + _save, which is a no-op)
    learner.reset_command("git diff")

    learner2 = Learner(str(tmp_path))
    e2 = learner2.data["entries"]["git diff"]
    assert e2["hot"] is False
    assert e2["confidence"] == INITIAL_CONFIDENCE
    assert e2["calls"] == 0
    assert learner2.lookup("git diff") is None


def test_handles_registry_missing_stats_key(tmp_path):
    """Older/partial registry.json (no 'stats' or 'entries' key) must not crash init."""
    import json
    d = tmp_path / ".clipress"
    d.mkdir()
    (d / "registry.json").write_text(json.dumps({"version": "1.0"}))

    learner = Learner(str(tmp_path))
    # Stats dict must be accessible without KeyError (no crash on missing keys)
    stats = learner.data["stats"]
    assert "total_commands_learned" in stats
    assert "total_tokens_saved" in stats
    assert stats["total_commands_learned"] == 0
    assert learner.data["entries"] == {}


def test_handles_non_dict_registry_payload(tmp_path):
    """A JSON array where a dict is expected must not crash init."""
    import json
    d = tmp_path / ".clipress"
    d.mkdir()
    (d / "registry.json").write_text(json.dumps(["not", "a", "dict"]))

    learner = Learner(str(tmp_path))
    assert isinstance(learner.data, dict)
    assert "stats" in learner.data and "entries" in learner.data
