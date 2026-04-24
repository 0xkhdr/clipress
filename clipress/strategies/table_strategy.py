import re
from typing import Any
from .base import BaseStrategy


class TableStrategy(BaseStrategy):
    _TABLE_SEP = re.compile(r"^[-\s|+]+$")

    def compress(
        self, output: str, params: dict[str, Any], contract: dict[str, Any]
    ) -> str:
        if not output:
            return output

        max_rows = params.get("max_rows", 20)
        max_columns = params.get("max_columns", 5)
        max_cell_length = params.get("max_cell_length", 40)

        original_lines = output.splitlines()

        lines = []

        header_idx = -1
        for i, ln in enumerate(original_lines):
            # Find header
            if ln.isupper():
                header_idx = i
                break
            if i + 1 < len(original_lines) and self._TABLE_SEP.match(
                original_lines[i + 1]
            ):
                header_idx = i
                break

        if header_idx != -1:
            # We have a header, let's keep it.
            # But the actual columns trimming requires parsing.
            # To keep it simple and robust, we just do line truncation for cells and rows.
            pass
        else:
            header_idx = 0  # Assume first line if no clear header

        # Truncate rows
        row_count = 0
        for i, line in enumerate(original_lines):
            if i <= header_idx:
                lines.append(line)
                continue
            if self._TABLE_SEP.match(line):
                lines.append(line)
                continue

            if line.strip():
                row_count += 1
                if row_count <= max_rows:
                    # re.split with a capturing group returns alternating [content, sep, content, sep, ...]
                    # Even indices (0, 2, 4, ...) are column content; odd indices are separators.
                    parts = re.split(r"(\s{2,}|\t)", line)
                    new_parts = []
                    col_count = 0
                    for i, p in enumerate(parts):
                        if i % 2 == 1:  # separator — always pass through
                            new_parts.append(p)
                        else:  # column content
                            col_count += 1
                            if col_count > max_columns:
                                break
                            new_parts.append(p[: max_cell_length - 3] + "..." if len(p) > max_cell_length else p)

                    lines.append("".join(new_parts))
                elif row_count == max_rows + 1:
                    lines.append("... [additional rows omitted]")

        final_lines = self._apply_contract(lines, original_lines, contract)
        result = "\n".join(final_lines)
        return result if result else output
