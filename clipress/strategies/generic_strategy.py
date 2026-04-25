import re
from collections import deque
from typing import Any
from .base import BaseStrategy


class GenericStrategy(BaseStrategy):
    def compress(
        self, output: str, params: dict[str, Any], contract: dict[str, Any]
    ) -> str:
        if not output:
            return output

        max_lines = params.get("max_lines", 50)
        head_lines = params.get("head_lines", 20)
        tail_lines = params.get("tail_lines", 10)

        # Clamp head + tail to max_lines so user-specified max_lines is always respected
        total_window = head_lines + tail_lines
        if total_window > max_lines:
            ratio = head_lines / total_window if total_window else 0.8
            head_lines = max(1, int(max_lines * ratio))
            tail_lines = max(0, max_lines - head_lines)
        dedup_min_repeats = params.get("dedup_min_repeats", 3)

        original_lines = output.splitlines()

        # Compile strip patterns early so we can apply them inline during the
        # rolling-window pass, avoiding a second full scan of the output.
        strip_patterns = [
            re.compile(p) for p in contract.get("always_strip", [])
        ]

        def _should_strip(line: str) -> bool:
            return any(p.search(line) for p in strip_patterns)

        # --- Rolling-window deduplication with bounded memory ---
        # We accumulate deduplicated lines into head (fixed list, max head_lines)
        # and tail (deque with fixed maxlen=tail_lines).  This bounds memory to
        # O(head_lines + tail_lines) regardless of how many lines the output has.
        head: list[str] = []
        tail: deque[str] = deque(maxlen=tail_lines if tail_lines > 0 else 1)
        total_deduped = 0  # count of lines after dedup (for omitted calculation)

        current_line: str | None = None
        repeat_count = 0

        def _emit(line: str) -> None:
            nonlocal total_deduped
            if _should_strip(line):
                return
            total_deduped += 1
            if len(head) < head_lines:
                head.append(line)
            else:
                tail.append(line)

        for raw_line in original_lines:
            line = raw_line.strip()
            if not line:
                continue

            if line == current_line:
                repeat_count += 1
            else:
                if current_line is not None:
                    if repeat_count >= dedup_min_repeats:
                        _emit(f"{current_line} [repeated {repeat_count}x]")
                    else:
                        for _ in range(repeat_count):
                            _emit(current_line)
                current_line = line
                repeat_count = 1

        if current_line is not None:
            if repeat_count >= dedup_min_repeats:
                _emit(f"{current_line} [repeated {repeat_count}x]")
            else:
                for _ in range(repeat_count):
                    _emit(current_line)

        # Build final line list with head + omission marker + tail
        if total_deduped > max_lines:
            tail_list = list(tail)
            omitted = total_deduped - len(head) - len(tail_list)
            if omitted > 0:
                lines = head + [f"... [{omitted} more lines]"] + tail_list
            else:
                lines = head + tail_list
        else:
            lines = head + list(tail)

        # Apply always_keep contract (always_strip was already applied inline)
        keep_patterns = contract.get("always_keep", [])
        if keep_patterns:
            kept = []
            for ln in original_lines:
                for p in keep_patterns:
                    if re.search(p, ln):
                        kept.append(ln)
                        break
            for ln in kept:
                if ln not in lines:
                    lines.append(ln)

        result = "\n".join(lines)
        return result if result else output
