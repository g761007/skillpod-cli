"""Default (identity) adapter — reproduces MVP behaviour for all three modes.

``IdentityAdapter`` applies no transformation to the skill directory; it
simply materialises ``target_dir`` from ``source_dir`` according to the
requested ``InstallMode``:

- ``SYMLINK``  : ``target_dir.symlink_to(source_dir)``
- ``COPY``     : ``shutil.copytree(source_dir, target_dir, symlinks=False)``
- ``HARDLINK`` : walk ``source_dir``, recreate directory structure, hardlink
                 each file with ``os.link()``.  File permissions are preserved.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from skillpod.installer.adapter import Adapter, InstallMode

logger = logging.getLogger(__name__)


class IdentityAdapter:
    """The built-in no-transformation adapter.

    Registered by default for every supported agent.  Projects that do not
    configure ``agents.<id>.adapter`` always use this class.
    """

    # Declare the type so type-checkers can verify Protocol conformance.
    _: Adapter

    def adapt(
        self,
        *,
        skill_name: str,
        source_dir: Path,
        target_dir: Path,
        mode: InstallMode,
    ) -> None:
        """Materialise ``target_dir`` from ``source_dir`` per ``mode``."""
        if mode is InstallMode.SYMLINK:
            target_dir.symlink_to(source_dir)
            logger.debug(
                "adapter.symlink skill=%s target=%s source=%s",
                skill_name,
                target_dir,
                source_dir,
            )

        elif mode is InstallMode.COPY:
            shutil.copytree(source_dir, target_dir, symlinks=False)
            logger.debug(
                "adapter.copy skill=%s target=%s source=%s",
                skill_name,
                target_dir,
                source_dir,
            )

        elif mode is InstallMode.HARDLINK:
            _hardlink_tree(source_dir, target_dir)
            logger.debug(
                "adapter.hardlink skill=%s target=%s source=%s",
                skill_name,
                target_dir,
                source_dir,
            )

        else:  # pragma: no cover
            raise ValueError(f"unsupported install mode: {mode!r}")

    @property
    def modes_supported(self) -> str:
        """Human-readable list of supported modes (for ``adapter list``)."""
        return "symlink, copy, hardlink"


def _hardlink_tree(source: Path, target: Path) -> None:
    """Recreate ``source`` directory tree under ``target`` using hardlinks.

    Directories are created as real directories.  For each regular file
    ``os.link(src, dst)`` is called so ``src`` and ``dst`` share an inode.
    File permissions are preserved by ``os.link`` on POSIX systems.
    """
    target.mkdir(parents=True, exist_ok=False)
    for item in source.rglob("*"):
        rel = item.relative_to(source)
        dst = target / rel
        if item.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.link(item, dst)


__all__ = ["IdentityAdapter"]
