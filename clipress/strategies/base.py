import re
from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseStrategy(ABC):

    @abstractmethod
    def compress(
        self, output: str, params: dict[str, Any], contract: dict[str, Any]
    ) -> str:
        """
        Compress the output string.

        Args:
            output:   Raw command output
            params:   Strategy-specific parameters from registry
            contract: User output contract (always_keep, always_strip)

        Returns:
            Compressed string. MUST be shorter than input
            OR equal to input if nothing to compress.
            MUST NEVER return empty string for non-empty input.
            MUST honor contract.always_keep patterns.
            MUST honor contract.always_strip patterns.
        """
        pass

    def _apply_contract(
        self, lines: list[str], original_lines: list[str], contract: dict[str, Any]
    ) -> list[str]:
        """
        Shared contract enforcement.
        All strategies call this as their final step.
        """
        keep_patterns = contract.get("always_keep", [])
        strip_patterns = contract.get("always_strip", [])

        # restore any always_keep lines that were stripped
        if keep_patterns:
            kept = []
            for ln in original_lines:
                for p in keep_patterns:
                    if re.search(p, ln):
                        kept.append(ln)
                        break

            # add back if not already present
            for line in kept:
                if line not in lines:
                    lines.append(line)

        # strip always_strip lines
        if strip_patterns:
            filtered_lines = []
            for ln in lines:
                should_strip = False
                for p in strip_patterns:
                    if re.search(p, ln):
                        should_strip = True
                        break
                if not should_strip:
                    filtered_lines.append(ln)
            lines = filtered_lines

        return lines

    def name(self) -> str:
        return self.__class__.__name__.replace("Strategy", "").lower()


class StreamStrategy:
    """
    Mixin for strategies that can process output line-by-line.

    Stateful — create a fresh instance per streaming operation.
    Compatible with safety.py line-level checks: callers may filter lines
    before passing them to process_line().
    """

    def process_line(self, line: str) -> Optional[str]:
        """
        Process one output line.

        Returns the (possibly transformed) line to emit immediately,
        or None to swallow the line.
        """
        raise NotImplementedError

    def finalize(self) -> list[str]:
        """
        Called once when the stream ends.

        Returns any trailing lines (e.g. the captured final status line).
        """
        return []

    def reset(self) -> None:
        """Reset internal state to allow reuse (not required by callers)."""
        pass
