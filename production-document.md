Based on a detailed comparison of the three documents, here are the gaps and improvements required to make `clipress` production‑ready, reliable, and aligned with the v1.1 audit plan. These cover both what v1.1 added over v1.0 and some further hardening that was not fully addressed even in the audit plan.

---

## 🔍 Key Improvements from v1.1 That Must Be Applied

### 1. Global ANSI Stripping & Dedicated `ansi.py` Module
- **Current state** (v1.0 / project doc): ANSI stripping is optional and handled per‑strategy.
- **Required change**: Strip ANSI globally in the engine **before** any other step (safety, classification, compression). This reduces code duplication, prevents strategies from processing escape codes, and speeds up compression.  
- New module `clipress/ansi.py` with a single fast regex.

### 2. Error Pass‑Through
- **Missing feature**: Raw error output should be left untouched to avoid losing diagnostic context.
- **Implementation**: Add `engine.pass_through_on_error` config (default `true`). When the classifier detects `"error"` shape with confidence ≥ 0.7, return the raw (ANSI‑stripped) output immediately after safety checks.

### 3. Per‑Command Contracts
- **Current**: Only global `always_keep` / `always_strip` rules.
- **Required**: Support per‑command overrides in `.compressor/config.yaml` under a `commands:` block, e.g.:
  ```yaml
  commands:
    "git status":
      always_keep: ["^On branch"]
  ```
  The base strategy’s `_apply_contract` must merge these into the contract dict.

### 4. User Extensions for Seed Registry
- **Current**: Seeds only from built‑in `seeds.json`.
- **Required**: Load `*.yaml` files from `.compressor/extensions/`, merge them into the seed registry with **user extensions overriding built‑ins**. Matching must be **longest command key first** to avoid shadowing (e.g., `docker ps -a` before `docker ps`).

### 5. `dedup` Parameter in List Strategy
- **Current**: `docker logs` seed specifies `"dedup": true` but the strategy ignores it.
- **Fix**: `ListStrategy` must accept a `dedup` boolean; when `True`, collapse consecutive identical lines to a single line with a repeat count.

### 6. Claude Code Hook Must Return a Valid JSON Envelope
- **Current**: `post_tool_use.py` outputs only the compressed text.
- **Required**: Always return `{"type": "tool_result", "content": "<compressed>"}` as a single JSON object. This is critical for Claude Code’s hook protocol.

### 7. Thread‑Safety Limitation Documented (But Not Mitigated)
- **New rule S‑8**: The compressor is not thread‑safe. This must be clearly stated in the README.  
  **Further improvement** (not in v1.1): Implement file locking (`fcntl`/`portalocker`) on `registry.json` writes and a `threading.Lock` around the hot cache to make it safe under concurrency — essential if AI agents run parallel bash commands.

### 8. Relaxed Performance Targets
- **Hot path latency**:  < 10 ms (was < 5 ms) — more realistic for production.
- **Cold path** still < 200 ms, warm < 50 ms, classifier < 20 ms.
- Update all performance tests accordingly.

### 9. Workspace File Permissions & Blocklist
- `.compressor/` must be `0700`, files `0600`.
- `.compressor-ignore` must be loaded and respected (each line a command prefix).
- `is_binary` now accepts a configurable `non_ascii_ratio`.

### 10. Configuration Enhancements
- `strip_ansi` (bool, global) and `pass_through_on_error` added to the schema.
- Extensions loading order and deep merge with defaults documented.

### 11. Documentation & Notices
- **Streaming limitation**: `clipress` requires full output; cannot handle live streams.
- **Thread safety warning** added to README.
- **Per‑agent environment setup** documented (e.g., `CLIPRESS_AGENT_MODE=true` for shell‑based agents).

---

## 🔧 Additional Gaps / Recommendations (Beyond v1.1)

| Gap | Risk | Recommendation |
|-----|------|----------------|
| **No output size limit** | OOM with extremely large command output | Add a configurable `max_output_bytes` (e.g., 10 MB). If exceeded, pass through and warn. |
| **Binary detection only checks first 512 bytes** | Binary data after 512 bytes may slip through | Extend scanning to a larger sample (4 KB) or re‑check if suspicious characters appear later. |
| **No concurrency protection for registry/hot cache** | Corrupted `registry.json` or lost updates when multiple processes run | Use `fcntl.flock()` for file writes and a `threading.Lock` for the hot cache dictionary. |
| **Hot cache lifetime** | In‑memory cache lost between agent sessions, cold start every time | Acceptable, but consider persisting a “hot list” to disk so the first call after a restart is still fast. |
| **Compressed output longer than input** | Possible if contracts force many lines | Engine should measure token count and return original if compression actually **increased** the size. |
| **Security: environment variable dumping** | `printenv` or `echo $SECRET` not caught by command check | The output‑side patterns already cover many secrets, but consider adding `printenv`, `declare -p`, `set` to sensitive commands. |
| **Learner atomic write lacks read‑modify‑write safety** | Two writers can race even with atomic rename | Use a lock file or transactional file approach (write‑to‑temp + rename is safe on POSIX, but only if readers read the file in one go; still no guarantee against concurrent writes). Locking is needed. |
| **No compressed‑output validation** | No guarantee that strategy returns non‑empty for non‑empty input | Add a post‑compression check: if original non‑empty and compressed empty, fall back to original. |

---

## 📋 Action Items for Production Readiness

1. **Implement all v1.1 component changes** (engine, safety, strategies, config, hooks, CLI).
2. **Add `ansi.py`, implement global stripping.**
3. **Enable error pass‑through and per‑command contracts.**
4. **Refactor Claude Code hook to output JSON envelope.**
5. **Apply file permissions and lock down workspace.**
6. **Add output size limit and concurrency locks.**
7. **Cover all new test cases** (blocklist, error pass‑through, extensions, etc.).
8. **Update README** with streaming limitation, thread‑safety, agent setup.
9. **Run full security & performance audit** against the updated criteria.

Applying these changes will bring the project in line with the production‑ready `v1.1` blueprint and make it genuinely safe, fast, and reliable for real‑world AI agent workflows.
