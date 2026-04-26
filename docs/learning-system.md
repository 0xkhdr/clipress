# Learning System

clipress maintains a three-tier knowledge base that improves with every command call. Proven commands skip classification entirely — the most expensive operation in the pipeline.

---

## Overview

| Tier | Storage | Scope | Latency |
| :--- | :--- | :--- | :--- |
| **Hot cache** | In-memory LRU | Per-process | Zero (dict lookup) |
| **Seed registry** | Bundled JSON + user YAML | Package-wide | O(1) key lookup |
| **Workspace learner** | SQLite (WAL) | Per-workspace | Single DB read |

Strategy resolution checks tiers in order. The first match wins; lower tiers are never consulted.

---

## Tier 1 — Hot Cache (in-memory, per-process)

An `OrderedDict` LRU cache (max 100 entries) protected by `threading.Lock`. Commands are promoted here when they reach:
- ≥ `hot_cache_threshold` calls (default: 10)
- confidence ≥ 0.85

Hot-cached commands skip classification entirely. This is the fastest possible path — a dict lookup in the current process.

The hot cache is **not persisted** — it rebuilds as commands are called within a session. The workspace learner (Tier 3) ensures warm-tier entries survive process restarts.

---

## Tier 2 — Seed Registry (built-in + user extensions)

Pre-defined strategies for common tools (`git`, `docker`, `pytest`, `kubectl`, `npm`, …) shipped in `clipress/registry/seeds.json`.

User extensions in `.clipress/extensions/*.yaml` are merged on top with `user_override: true`, meaning user rules always win over built-in seeds.

Seeds are sorted **longest-key-first** so `docker ps -a` matches before `docker ps`.

See the full seed list in [compression.md](compression.md#built-in-seed-commands).

---

## Tier 3 — Workspace Learner (persistent, SQLite)

Stored in `.clipress/registry.db` (SQLite with WAL mode). Each command gets a row:

```json
{
  "git log": {
    "source": "learned",
    "strategy": "list",
    "calls": 42,
    "confidence": 0.92,
    "avg_raw_tokens": 1024,
    "avg_compressed_tokens": 256,
    "compression_ratio": 0.25,
    "hot": true,
    "user_override": false,
    "last_seen": "2026-04-25T12:34:56Z",
    "params": {}
  }
}
```

The learner uses **SQLite WAL mode** for concurrent-safe reads and writes. Multiple simultaneous clipress processes (e.g., parallel bash calls from an agent) are safe.

---

## Warm Tier

Once a command reaches **≥3 calls** with **≥0.65 confidence**, it activates as a **warm entry** — no classifier run needed on subsequent calls.

| Call count | Behavior | Overhead |
| :--- | :--- | :--- |
| ≤2 calls | Run classifier (heuristics) | Classifier cost |
| **3+ calls, confidence ≥0.65** | **Warm tier — skip classifier** | ~70% faster |
| 10+ calls, confidence ≥0.85 | Promote to hot cache (in-memory) | Zero latency |

After just 3 `git log` invocations, the 4th call skips classification entirely. Warm entries persist in SQLite, so they survive process restarts.

---

## Confidence Mechanics

Confidence tracks how consistently a command produces the same output shape.

| Event | Delta |
| :--- | :--- |
| Strategy matches previous | `+0.08` |
| Strategy differs | `−0.20` |
| Confidence drops below `0.50` | reset to `0.50`, adopt new strategy |
| Confidence ≥ `0.85` AND calls ≥ `hot_cache_threshold` | promote to hot cache |
| Confidence ≥ `0.95` | locked — stops updating |

The asymmetry (−0.20 vs +0.08) means wrong predictions degrade confidence faster than correct ones restore it. This prevents the learner from sticking with a mismatched strategy.

### Confidence thresholds at a glance

| Range | Effect |
| :--- | :--- |
| < 0.65 | Classifier runs, entry not used |
| 0.65 – 0.84 | Warm tier active (classifier skipped) |
| ≥ 0.85 (+ calls ≥ threshold) | Eligible for hot cache |
| ≥ 0.95 | Locked |

---

## Fuzzy Command Matching

Command variations automatically share cached strategies via **base-command matching**:

```
git log --oneline -100    ─┐
git log --oneline -50     ─┼─→  All use the "git log" cache entry
git log -p --reverse -20  ─┘
```

Only the **first 2–3 words** of a command are used for cache lookup. All flag variations hit the same registry entry.

After 3 total calls to any variant, warm cache activates for all of them. This reduces cold-path invocations by **30–50%** in typical workflows.

To override base matching with a command-specific rule:

```yaml
# .clipress/extensions/custom.yaml
"git log --all":
  strategy: list
  params:
    max_lines: 40
```

Longer keys always win — `git log --all` takes priority over `git log` for that specific invocation.

---

## Managing the Registry

```bash
# View all learned entries as JSON
clipress learn show

# Reset confidence for a specific command
clipress learn reset "git log"

# Reset all learned data
clipress learn reset

# View token savings summary
clipress report
```

---

## Registry Safety

- **WAL mode**: Multiple concurrent clipress processes read and write without locking conflicts
- **Automatic migration**: Legacy `registry.json` is imported into `registry.db` on first run and renamed to `registry.json.migrated`
- **Concurrent writers**: The in-memory hot cache uses `threading.Lock`; the SQLite learner uses WAL for process-level concurrency
