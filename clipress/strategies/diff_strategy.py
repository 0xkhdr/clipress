import re
from typing import Any
from .base import BaseStrategy


class DiffStrategy(BaseStrategy):
    _ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    def compress(
        self, output: str, params: dict[str, Any], contract: dict[str, Any]
    ) -> str:
        if not output:
            return output

        max_lines = params.get("max_lines", 80)
        context_lines = params.get("context_lines", 2)

        clean_output = self._ANSI_ESCAPE.sub("", output)
        original_lines = clean_output.splitlines()

        lines = []

        # Pass 1: find which lines to keep based on +/-/@@/+++/--- and context
        keep_indices = set()
        for i, line in enumerate(original_lines):
            if (
                line.startswith("+++")
                or line.startswith("---")
                or line.startswith("@@")
            ):
                keep_indices.add(i)
            elif line.startswith("+") or line.startswith("-"):
                # keep this line and context
                for j in range(
                    max(0, i - context_lines),
                    min(len(original_lines), i + context_lines + 1),
                ):
                    keep_indices.add(j)

        # Pass 2: filter
        for i, line in enumerate(original_lines):
            if line.startswith("index "):
                continue  # strip index metadata

            if i in keep_indices:
                lines.append(line)

        # If too large, summarize by file
        if len(lines) > max_lines:
            files_changed = {}
            current_file = None
            additions = 0
            deletions = 0

            for line in original_lines:
                if line.startswith("+++ b/"):
                    if current_file:
                        files_changed[current_file] = (additions, deletions)
                    current_file = line[6:]
                    additions = 0
                    deletions = 0
                elif line.startswith("+") and not line.startswith("+++"):
                    additions += 1
                elif line.startswith("-") and not line.startswith("---"):
                    deletions += 1

            if current_file:
                files_changed[current_file] = (additions, deletions)

            if files_changed:
                lines = ["[Diff too large, summarized by file]"]
                for f, (add, delete) in files_changed.items():
                    lines.append(f"{f}: +{add} -{delete}")

        final_lines = self._apply_contract(lines, original_lines, contract)
        result = "\n".join(final_lines)
        return result if result else output
