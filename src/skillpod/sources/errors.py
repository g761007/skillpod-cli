"""Typed errors for the source-resolver capability."""

from __future__ import annotations


class SourceError(Exception):
    """Base error for source resolution failures."""


class SourceNotFound(SourceError):
    """A skill could not be located in any declared source (or registry)."""


class GitOperationError(SourceError):
    """A git invocation failed (clone, checkout, rev-parse, ls-remote)."""


__all__ = ["GitOperationError", "SourceError", "SourceNotFound"]
