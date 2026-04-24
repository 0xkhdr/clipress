import re
from typing import Any
from .base import BaseStrategy


class KeyvalueStrategy(BaseStrategy):
    _KV1 = re.compile(r"^(\s*\w[\w\s]*):\s+(\S.*)$")
    _KV2 = re.compile(r"^(\s*\w[\w\s]*)=\s*(\S.*)$")
    _TIMESTAMP = re.compile(r"time|date|at", re.IGNORECASE)

    def compress(
        self, output: str, params: dict[str, Any], contract: dict[str, Any]
    ) -> str:
        if not output:
            return output

        max_lines = params.get("max_lines", 20)
        strip_keys = params.get("always_strip_keys", [])

        original_lines = output.splitlines()

        lines = []
        kv_pairs = []

        for line in original_lines:
            m = self._KV1.match(line) or self._KV2.match(line)
            if m:
                key = m.group(1).strip()
                if any(re.search(sk, key) for sk in strip_keys):
                    continue
                kv_pairs.append((key, line))
            else:
                kv_pairs.append((None, line))

        if len(kv_pairs) > max_lines:
            # keep most relevant (non-timestamp keys)
            important = []
            for k, ln in kv_pairs:
                if k is None or not self._TIMESTAMP.search(k):
                    important.append(ln)

            if len(important) > max_lines:
                lines = important[:max_lines] + ["... [additional pairs omitted]"]
            else:
                lines = important + ["... [timestamp pairs omitted]"]
        else:
            lines = [ln for k, ln in kv_pairs]

        final_lines = self._apply_contract(lines, original_lines, contract)
        result = "\n".join(final_lines)
        return result if result else output
