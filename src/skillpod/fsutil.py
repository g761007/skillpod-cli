"""Filesystem helpers that behave the same on every supported platform."""

from __future__ import annotations

import shutil
import stat
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any


def _make_writable(path: Path) -> None:
    """Add the owner-write bit, keeping every other permission intact.

    Assigning a bare ``stat.S_IWRITE`` would *replace* the mode with 0o200,
    leaving a directory write-only and therefore untraversable — which breaks
    the very removal this is trying to unblock.
    """
    try:
        mode = path.stat().st_mode
    except OSError:
        return
    extra = stat.S_IWUSR | (stat.S_IXUSR if stat.S_ISDIR(mode) else 0)
    with suppress(OSError):
        path.chmod(mode | extra)


def _clear_readonly_and_retry(func: Any, path: str, *_ignored: Any) -> None:
    """Make the failing path removable, then retry.

    Two different rules have to be satisfied, and which one bites depends on
    the platform:

    - **POSIX** decides whether a file may be unlinked from its *parent
      directory's* permissions, so a read-only directory blocks removal of
      everything inside it.
    - **Windows** additionally honours the file's own read-only attribute and
      raises ``WinError 5``.

    Both are cleared, because both occur in practice: git marks everything
    under ``.git/objects/`` read-only, and skillpod copies whole repositories
    when a repo's root *is* the skill. Replacing such a skill — exactly what
    ``skillpod global update`` does — hit this on Windows.
    """
    target = Path(path)
    _make_writable(target.parent)
    _make_writable(target)
    func(path)


def rmtree(path: str | Path) -> None:
    """``shutil.rmtree`` that can also remove write-protected content."""
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_clear_readonly_and_retry)
    else:  # pragma: no cover - exercised on 3.11 only
        shutil.rmtree(path, onerror=_clear_readonly_and_retry)


__all__ = ["rmtree"]
