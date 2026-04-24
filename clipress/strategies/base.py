import re
from abc import ABC, abstractmethod
from typing import Any


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
            # We want to find which original lines matched keep_patterns
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
