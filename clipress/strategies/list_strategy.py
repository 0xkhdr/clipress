import os
from typing import Any
from .base import BaseStrategy


class ListStrategy(BaseStrategy):
    def compress(
        self, output: str, params: dict[str, Any], contract: dict[str, Any]
    ) -> str:
        if not output:
            return output

        max_lines = params.get("max_lines", 30)
        head_lines = params.get("head_lines", 20)
        tail_lines = params.get("tail_lines", 5)
        group_by_dir = params.get("group_by_directory", False)
        dedup = params.get("dedup", False)

        original_lines = output.splitlines()

        # Strip blank lines but preserve original for contract
        lines = [ln for ln in original_lines if ln.strip()]

        if dedup:
            deduped_lines = []
            current_line = None
            repeat_count = 0
            for line in lines:
                if line == current_line:
                    repeat_count += 1
                else:
                    if current_line is not None:
                        if repeat_count > 1:
                            deduped_lines.append(f"{current_line} [repeated {repeat_count}x]")
                        else:
                            deduped_lines.append(current_line)
                    current_line = line
                    repeat_count = 1
            if current_line is not None:
                if repeat_count > 1:
                    deduped_lines.append(f"{current_line} [repeated {repeat_count}x]")
                else:
                    deduped_lines.append(current_line)
            lines = deduped_lines

        if group_by_dir:
            # Group by directory heuristic for paths
            dirs: dict[str, list[str]] = {}
            others = []
            for line in lines:
                if "/" in line or "\\" in line:
                    d = os.path.dirname(line)
                    if d not in dirs:
                        dirs[d] = []
                    dirs[d].append(line)
                else:
                    others.append(line)

            # If we successfully grouped some, replace lines with groups
            if dirs:
                grouped_lines = []
                for d, files in dirs.items():
                    if len(files) > 3:
                        grouped_lines.append(f"{d}/... [{len(files)} files]")
                    else:
                        grouped_lines.extend(files)
                lines = others + grouped_lines

        # Clamp head + tail to max_lines so user-specified max_lines is always respected
        total_window = head_lines + tail_lines
        if total_window > max_lines:
            ratio = head_lines / total_window if total_window else 0.8
            head_lines = max(1, int(max_lines * ratio))
            tail_lines = max(0, max_lines - head_lines)

        if len(lines) <= max_lines:
            pass  # Keep as is
        else:
            head = lines[:head_lines]
            tail = lines[-tail_lines:] if tail_lines > 0 else []
            omitted = len(lines) - head_lines - tail_lines
            if omitted > 0:
                lines = head + [f"... [{omitted} more items]"] + tail

        final_lines = self._apply_contract(lines, original_lines, contract)
        result = "\n".join(final_lines)
        return result if result else output
