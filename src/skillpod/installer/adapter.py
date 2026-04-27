"""Adapter protocol and install-mode enum for the fan-out pipeline.

The ``Adapter`` protocol defines the single method every adapter must implement.
``InstallMode`` enumerates the three supported materialisation strategies.

Contract (from design.md):
- The installer guarantees ``target_dir`` does not exist when ``adapt()`` is called.
- The adapter MAY return early without creating ``target_dir`` (skip), but MUST
  log a structured reason so ``doctor`` can explain the absence later.
- The adapter MUST NOT touch ``source_dir``.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Protocol


class InstallMode(StrEnum):
    """Materialisation strategy for a fan-out entry."""

    SYMLINK = "symlink"
    COPY = "copy"
    HARDLINK = "hardlink"


class Adapter(Protocol):
    """Render ``.skillpod/skills/<name>/`` into ``.<agent>/skills/<name>/``."""

    def adapt(
        self,
        *,
        skill_name: str,
        source_dir: Path,
        target_dir: Path,
        mode: InstallMode,
    ) -> None:
        """Materialise ``target_dir`` from ``source_dir`` using ``mode``.

        Parameters
        ----------
        skill_name:
            Name of the skill being materialised (for logging).
        source_dir:
            Canonical source: ``.skillpod/skills/<name>/``.  MUST NOT be
            modified by the adapter.
        target_dir:
            Per-agent destination: ``.<agent>/skills/<name>/``.  Does not
            exist when this method is called.
        mode:
            Requested materialisation strategy.
        """
        ...


__all__ = ["Adapter", "InstallMode"]
