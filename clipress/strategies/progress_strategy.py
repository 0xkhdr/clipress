import re
from typing import Any
from .base import BaseStrategy


class ProgressStrategy(BaseStrategy):
    _PCT_ONLY = re.compile(r"^\s*\d+%\s*$")
    _ETA_SPEED = re.compile(r"eta|speed|\d+\s*[kmg]b/s", re.IGNORECASE)
    _ERROR = re.compile(r"error|fail|exception", re.IGNORECASE)

    def compress(
        self, output: str, params: dict[str, Any], contract: dict[str, Any]
    ) -> str:
        if not output:
            return output

        keep_mode = params.get("keep", "final_line")
        strip_pct = params.get("strip_percentage", True)

        original_lines = output.splitlines()

        lines = []
        errors = []
        final_line = ""

        for line in original_lines:
            ln = line.strip()
            if not ln:
                continue

            final_line = line

            if self._ERROR.search(line):
                errors.append(line)
                continue

            if strip_pct and (
                self._PCT_ONLY.match(line) or "%" in line and len(line) < 15
            ):
                continue

            if self._ETA_SPEED.search(line):
                continue

            lines.append(line)

        result_lines = []
        if keep_mode == "errors_and_final":
            result_lines.extend(errors)
            if final_line and final_line not in result_lines:
                result_lines.append(final_line)
        elif keep_mode == "final_line":
            result_lines.extend(errors)  # Always keep errors per spec
            if final_line and final_line not in result_lines:
                result_lines.append(final_line)
        else:  # e.g. keep all non-stripped
            result_lines = lines
            # Ensure errors and final line are included if not present
            for e in errors:
                if e not in result_lines:
                    result_lines.append(e)
            if final_line and final_line not in result_lines:
                result_lines.append(final_line)

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for r in result_lines:
            if r not in seen:
                deduped.append(r)
                seen.add(r)

        final_lines = self._apply_contract(deduped, original_lines, contract)
        result = "\n".join(final_lines)
        return result if result else output
