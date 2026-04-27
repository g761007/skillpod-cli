"""Typed errors for the registry-discovery capability."""

from __future__ import annotations


class RegistryError(Exception):
    """Base error for any registry lookup failure."""


class RegistryUnavailable(RegistryError):
    """Network failure or a non-2xx HTTP response from the registry."""


class RegistryNotFound(RegistryError):
    """The registry returned 404 for the requested skill."""


class RegistryMalformed(RegistryError):
    """The registry response was unparseable or missing required fields."""


__all__ = [
    "RegistryError",
    "RegistryMalformed",
    "RegistryNotFound",
    "RegistryUnavailable",
]
