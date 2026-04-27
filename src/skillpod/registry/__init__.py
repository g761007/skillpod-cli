"""Registry-discovery capability: read-only skills.sh client."""

from skillpod.registry.errors import (
    RegistryError,
    RegistryMalformed,
    RegistryNotFound,
    RegistryUnavailable,
)
from skillpod.registry.skills_sh import DEFAULT_BASE_URL, RepoInfo, lookup
from skillpod.registry.trust import TrustError, enforce

__all__ = [
    "DEFAULT_BASE_URL",
    "RegistryError",
    "RegistryMalformed",
    "RegistryNotFound",
    "RegistryUnavailable",
    "RepoInfo",
    "TrustError",
    "enforce",
    "lookup",
]
