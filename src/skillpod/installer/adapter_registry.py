"""Module-level adapter registry.

Maps ``agent_id -> Adapter`` instance.  The default mapping contains an
``IdentityAdapter`` for every supported agent.

Functions
---------
get_adapter(agent)
    Return the registered adapter for ``agent``, defaulting to
    ``IdentityAdapter``.
register_adapter(agent, adapter)
    Override the adapter for ``agent`` (used by manifest-driven imports).
reset_registry()
    Restore the default mapping (for use in tests).
"""

from __future__ import annotations

from skillpod.installer.adapter import Adapter
from skillpod.installer.adapter_default import IdentityAdapter
from skillpod.manifest.models import SUPPORTED_AGENTS

# Module-level mutable registry — one IdentityAdapter per supported agent.
_REGISTRY: dict[str, Adapter] = {agent: IdentityAdapter() for agent in SUPPORTED_AGENTS}


def get_adapter(agent: str) -> Adapter:
    """Return the registered adapter for ``agent``.

    Falls back to a fresh ``IdentityAdapter`` when ``agent`` has no explicit
    registration (should not happen for agents in ``SUPPORTED_AGENTS``, but
    keeps the API robust for forward-compatibility).
    """
    return _REGISTRY.get(agent, IdentityAdapter())


def register_adapter(agent: str, adapter: Adapter) -> None:
    """Register ``adapter`` as the handler for ``agent``.

    Called by the install pipeline before fan-out when the manifest
    declares ``agents.<id>.adapter: dotted.path``.
    """
    _REGISTRY[agent] = adapter


def reset_registry() -> None:
    """Restore the default registry.  Used in test teardown."""
    _REGISTRY.clear()
    _REGISTRY.update({agent: IdentityAdapter() for agent in SUPPORTED_AGENTS})


__all__ = ["get_adapter", "register_adapter", "reset_registry"]
