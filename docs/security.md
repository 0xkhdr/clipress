# Security

clipress never compresses output that may contain secrets, credentials, or sensitive data. When any safety condition is triggered, the original output is returned unchanged.

---

## Automatic Pass-Through Conditions

| Condition | Behavior |
| :--- | :--- |
| Output > `max_output_bytes` (default 10 MB) | Pass through, warn to stderr |
| Command in blocklist (`.clipress-ignore`) | Pass through |
| Security pattern matched | Pass through |
| Binary output detected | Pass through |
| Output < `min_lines_to_compress` (default 15) | Pass through |
| Error shape + `pass_through_on_error=true` | Pass through |

---

## Built-In Security Patterns

The following patterns are always checked (case-insensitive, word-boundary aware):

| Category | Patterns | Match type |
| :--- | :--- | :--- |
| **Credential files** | `.env*`, `*.pem`, `*.key`, `id_rsa`, `id_ed25519` | Filename match |
| **Secret keywords** | `credentials`, `secret`, `password`, `api_key`, `api-key` | Word boundary match |
| **Token patterns** | `AWS_SECRET`, `GITHUB_TOKEN`, `bearer <token>`, `-----BEGIN` | Content match |
| **Sensitive commands** | `printenv`, `declare`, `env`, `set` | Unconditionally blocked |

Word-boundary matching (`\bsecret\b`, `\bpassword\b`, etc.) prevents false positives — words like "secretary" do not trigger the gate.

Commands like `printenv`, `env`, `declare`, and `set` are **unconditionally blocked** — their output is never compressed, regardless of content.

---

## Adding Project-Specific Patterns

```yaml
# .clipress/config.yaml
safety:
  security_patterns:
    - "MY_INTERNAL_SECRET"
    - "PROD_DB_PASSWORD"
    - "INTERNAL_API_KEY"
```

User-supplied patterns are compiled and applied **on top of** the built-in list. They follow the same case-insensitive matching rules.

---

## Binary Detection

Outputs with:
- Null bytes (`\x00`), or
- A non-ASCII character ratio above `binary_non_ascii_ratio` (default 0.30) in the first 4 KB

are treated as binary and passed through unchanged.

To adjust the threshold:

```yaml
# .clipress/config.yaml
safety:
  binary_non_ascii_ratio: 0.2   # stricter — flag binary earlier
```

---

## Error Handling Philosophy

clipress is a compressor, not a validator. It must never crash the agent or block legitimate commands. The engine wraps the entire pipeline in a top-level `try/except` and returns the original output on any failure.

Set `CLIPRESS_DEBUG=1` to surface suppressed errors to stderr:

```bash
CLIPRESS_DEBUG=1 some_command | clipress compress "some_command"
```

This is useful for diagnosing unexpected pass-throughs or misconfigured patterns.

---

## Blocklist

The `.clipress/.clipress-ignore` file lists command prefixes that are always passed through uncompressed:

```
# .clipress/.clipress-ignore
kubectl exec
psql
mysql
```

Any command starting with a listed prefix is passed through. Use this for interactive tools, database clients, or any command whose output should never be modified.

See [configuration.md](configuration.md#blocklist) for the full format.

---

## ANSI Guard (O(1) Optimization)

Before running full ANSI escape code stripping, clipress checks for common ANSI prefixes in constant time:

```python
if output.find('\033[') == -1 and output.find('[') == -1:
    # No ANSI codes detected — skip regex entirely
    pass
else:
    output = ansi.strip(output)
```

90% of real-world outputs skip the regex entirely. Set `strip_ansi: false` in config if you never receive ANSI codes and want to skip the prefix check too.
