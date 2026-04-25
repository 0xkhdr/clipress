from typing import Any, Optional
from .generic_strategy import GenericStrategy
from .list_strategy import ListStrategy
from .progress_strategy import ProgressStrategy, ProgressStreamStrategy
from .test_strategy import TestStrategy
from .diff_strategy import DiffStrategy
from .table_strategy import TableStrategy
from .keyvalue_strategy import KeyvalueStrategy
from .error_strategy import ErrorStrategy
from .base import StreamStrategy

STRATEGIES = {
    "generic": GenericStrategy(),
    "list": ListStrategy(),
    "progress": ProgressStrategy(),
    "test": TestStrategy(),
    "diff": DiffStrategy(),
    "table": TableStrategy(),
    "keyvalue": KeyvalueStrategy(),
    "error": ErrorStrategy(),
}


def get_strategy(name: str):
    return STRATEGIES.get(name, STRATEGIES["generic"])


def get_stream_strategy_instance(name: str, params: dict[str, Any]) -> Optional[StreamStrategy]:
    """Return a fresh stateful streaming strategy, or None if not supported."""
    if name == "progress":
        return ProgressStreamStrategy(params)
    return None
