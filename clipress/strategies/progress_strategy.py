import re
from typing import Any, Optional
from .base import BaseStrategy, StreamStrategy


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
        else:  # keep all non-stripped
            result_lines = lines
            for e in errors:
                if e not in result_lines:
                    result_lines.append(e)
            if final_line and final_line not in result_lines:
                result_lines.append(final_line)

        # Deduplicate while preserving order
        seen: set[str] = set()
        deduped = []
        for r in result_lines:
            if r not in seen:
                deduped.append(r)
                seen.add(r)

        final_lines = self._apply_contract(deduped, original_lines, contract)
        result = "\n".join(final_lines)
        return result if result else output


class ProgressStreamStrategy(StreamStrategy):
    """
    Stateful, line-by-line streaming variant of ProgressStrategy.

    Instantiate fresh per streaming operation. Errors are emitted immediately;
    progress spam is swallowed; the final non-spam line is held until finalize().
    """

    _PCT_ONLY = re.compile(r"^\s*\d+%\s*$")
    _ETA_SPEED = re.compile(r"eta|speed|\d+\s*[kmg]b/s", re.IGNORECASE)
    _ERROR = re.compile(r"error|fail|exception", re.IGNORECASE)

    def __init__(self, params: dict[str, Any]) -> None:
        self._keep_mode: str = params.get("keep", "final_line")
        self._strip_pct: bool = params.get("strip_percentage", True)
        self._errors: list[str] = []
        self._last_significant: str = ""

    def process_line(self, line: str) -> Optional[str]:
        ln = line.strip()
        if not ln:
            return None

        # Errors are emitted immediately and remembered for finalize
        if self._ERROR.search(line):
            self._errors.append(line)
            return line

        # Swallow progress spam
        if self._strip_pct:
            if self._PCT_ONLY.match(line) or ("%" in line and len(ln) < 15):
                return None

        if self._ETA_SPEED.search(line):
            return None

        # Keep last significant non-spam line for finalize()
        self._last_significant = line
        return None  # Buffer until finalize so we can reliably emit "final line"

    def finalize(self) -> list[str]:
        """Emit the captured final line (if not already emitted as an error)."""
        result: list[str] = []
        if self._last_significant and self._last_significant not in self._errors:
            result.append(self._last_significant)
        return result

    def reset(self) -> None:
        self._errors = []
        self._last_significant = ""
