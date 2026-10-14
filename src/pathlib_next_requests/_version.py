"""The version of the installed distribution."""

from __future__ import annotations

from importlib import metadata as _metadata

try:
    __version__ = _metadata.version("pathlib-next-requests")
except _metadata.PackageNotFoundError:
    # Run from a source tree that was never installed.
    __version__ = "0+unknown"
