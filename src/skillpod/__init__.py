"""skillpod — project-scoped, reproducible skill dependency manager."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("skillpod")
except PackageNotFoundError:  # not installed (e.g. source tree without dist metadata)
    __version__ = "0.0.0+dev"
