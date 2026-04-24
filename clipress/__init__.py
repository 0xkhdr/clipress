"""
clipress - Universal CLI output compressor for AI agents
"""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("clipress")
except PackageNotFoundError:
    # Running from a source checkout without an installed distribution.
    __version__ = "0+unknown"
