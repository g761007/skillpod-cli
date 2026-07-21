"""Typed errors for the installer pipeline."""

from __future__ import annotations


class InstallError(Exception):
    """Base class for install pipeline failures.

    Carries an `exit_code` so the CLI can map errors to stable exit codes
    without re-classifying them.
    """

    exit_code: int = 1


class InstallUserError(InstallError):
    """User-actionable failure: manifest invalid, conflicting symlinks."""

    exit_code = 1


class InstallSystemError(InstallError):
    """System / network failure: registry unreachable, git failure,
    filesystem permission denied."""

    exit_code = 2


class InstallConflict(InstallUserError):
    """Refusal to overwrite an unmanaged path during fan-out."""


class AdapterImportError(InstallUserError):
    """A custom adapter dotted path could not be imported or resolved.

    Raised before any filesystem mutation so no partial installs occur.
    """


__all__ = [
    "AdapterImportError",
    "InstallConflict",
    "InstallError",
    "InstallSystemError",
    "InstallUserError",
]
