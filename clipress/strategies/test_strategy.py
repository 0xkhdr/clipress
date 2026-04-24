import re
from typing import Any
from .base import BaseStrategy


class TestStrategy(BaseStrategy):
    _PASS = re.compile(r"\b(PASSED|ok|✓)\b")
    _FAIL = re.compile(r"\b(FAILED|FAIL|ERROR|✗)\b")
    _SUMMARY = re.compile(r"==+|---|total:|passed:|failed:")

    def compress(
        self, output: str, params: dict[str, Any], contract: dict[str, Any]
    ) -> str:
        if not output:
            return output

        max_traceback = params.get("max_traceback_lines", 8)
        keep = params.get("keep", "failed_only")  # usually failed_only

        original_lines = output.splitlines()

        lines = []
        in_traceback = False
        traceback_count = 0
        summary_lines = []

        # Heuristic: the last few lines are often summary
        non_empty = [ln for ln in original_lines if ln.strip()]
        if non_empty:
            for ln in non_empty[-5:]:
                if self._SUMMARY.search(ln) or (
                    ("failed" in ln.lower() or "passed" in ln.lower()) and "====" in ln
                ):
                    summary_lines.append(ln)
            if not summary_lines:
                summary_lines.append(non_empty[-1])

        for line in original_lines:
            ln = line.strip()
            if not ln:
                continue

            if line in summary_lines:
                continue  # we will add them at the end

            # Check if this line is a failure or pass
            is_fail = bool(self._FAIL.search(line))
            is_pass = bool(self._PASS.search(line))

            if is_fail:
                lines.append(line)
                in_traceback = True
                traceback_count = 0
                continue
            elif is_pass:
                in_traceback = False
                if keep == "all":
                    lines.append(line)
                continue

            # It's some other output
            if in_traceback:
                if traceback_count < max_traceback:
                    lines.append(line)
                    traceback_count += 1
                elif traceback_count == max_traceback:
                    lines.append("... [traceback truncated]")
                    traceback_count += 1

        # Deduplicate assertion messages (very simplistic approach)
        deduped = []
        seen = set()
        for line in lines:
            if "AssertionError:" in line or "expect(" in line:
                if line in seen:
                    continue
                seen.add(line)
            deduped.append(line)

        deduped.extend(summary_lines)

        final_lines = self._apply_contract(deduped, original_lines, contract)
        result = "\n".join(final_lines)
        return result if result else output
