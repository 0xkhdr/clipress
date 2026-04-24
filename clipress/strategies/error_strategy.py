from typing import Any
from .base import BaseStrategy


class ErrorStrategy(BaseStrategy):

    def compress(
        self, output: str, params: dict[str, Any], contract: dict[str, Any]
    ) -> str:
        if not output:
            return output

        max_traceback = params.get("max_traceback_lines", 10)
        strip_stdlib = params.get("strip_stdlib_frames", True)

        original_lines = output.splitlines()

        lines = []
        frames_kept = 0
        in_traceback = False

        # We need to keep the exception header (e.g. Traceback...)
        # and the final exception message
        # We strip duplicate frames and noisy paths.

        last_line = ""
        for i, line in enumerate(original_lines):
            ln = line.strip()
            if not ln:
                continue

            if "Traceback" in line or "Exception" in line:
                in_traceback = True
                lines.append(line)
                continue

            if in_traceback:
                if 'File "' in line or "at line" in line or ln.startswith("at "):
                    # It's a frame
                    if strip_stdlib and (
                        "site-packages" in line or "/usr/lib/python" in line
                    ):
                        # skip it and the next line (the code snippet)
                        continue
                    if frames_kept < max_traceback:
                        if line != last_line:
                            lines.append(line)
                            frames_kept += 1
                            last_line = line
                    elif frames_kept == max_traceback:
                        lines.append("... [additional frames omitted]")
                        frames_kept += 1
                elif line.startswith("    ") or line.startswith(
                    "\t"
                ):  # frame code snippet
                    if lines and "omitted" not in lines[-1]:
                        lines.append(line)
                else:  # Could be the exception message itself
                    lines.append(line)
                    in_traceback = False  # might be end of it
            else:
                lines.append(line)

        # Deduplicate caused by chain
        deduped: list[str] = []
        for line in lines:
            if deduped and line == deduped[-1] and "Caused by" in line:
                continue
            deduped.append(line)

        final_lines = self._apply_contract(deduped, original_lines, contract)
        result = "\n".join(final_lines)
        return result if result else output
