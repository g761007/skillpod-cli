"""Profile-related user-visible errors."""

from __future__ import annotations


class ProfileError(Exception):
    """Raised for profile operations that fail due to user error."""


__all__ = ["ProfileError"]
