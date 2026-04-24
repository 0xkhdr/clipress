from typing import Any
from .base import BaseStrategy


class GenericStrategy(BaseStrategy):
    def compress(
        self, output: str, params: dict[str, Any], contract: dict[str, Any]
    ) -> str:
        if not output:
            return output

        # defaults
        max_lines = params.get("max_lines", 50)
        head_lines = params.get("head_lines", 20)
        tail_lines = params.get("tail_lines", 10)
        dedup_min_repeats = params.get("dedup_min_repeats", 3)

        # 2. Strip blank lines and deduplicate
        original_lines = output.splitlines()
        lines = []

        current_line = None
        repeat_count = 0

        for raw_line in original_lines:
            line = raw_line.strip()
            if not line:
                continue

            if line == current_line:
                repeat_count += 1
            else:
                if current_line is not None:
                    if repeat_count >= dedup_min_repeats:
                        lines.append(f"{current_line} [repeated {repeat_count}x]")
                    else:
                        for _ in range(repeat_count):
                            lines.append(current_line)

                current_line = line
                repeat_count = 1

        if current_line is not None:
            if repeat_count >= dedup_min_repeats:
                lines.append(f"{current_line} [repeated {repeat_count}x]")
            else:
                for _ in range(repeat_count):
                    lines.append(current_line)

        # 4. If lines > max_lines: truncate with head+tail
        if len(lines) > max_lines:
            head = lines[:head_lines]
            tail = lines[-tail_lines:] if tail_lines > 0 else []
            omitted = len(lines) - head_lines - tail_lines
            if omitted > 0:
                lines = head + [f"... [{omitted} more lines]"] + tail

        # 5. Apply contract
        final_lines = self._apply_contract(lines, original_lines, contract)

        result = "\n".join(final_lines)
        return result if result else output
