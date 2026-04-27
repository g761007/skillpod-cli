"""Symlink creation with rollback + safety checks."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from contextlib import contextmanager, suppress
from pathlib import Path

from skillpod.installer.errors import InstallConflict, InstallSystemError
from skillpod.installer.paths import is_managed_fanout


@contextmanager
def rollback_on_failure() -> Iterable[Callable[[Path], None]]:
    """Track filesystem actions; undo them all if the block raises."""
    created: list[Path] = []

    def record(path: Path) -> None:
        created.append(path)

    try:
        yield record
    except BaseException:
        for path in reversed(created):
            with suppress(OSError):
                if path.is_symlink() or path.exists():
                    if path.is_symlink() or path.is_file():
                        path.unlink(missing_ok=True)
                    elif path.is_dir():
                        with suppress(OSError):
                            path.rmdir()
        raise


def _create_symlink(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target)
    except OSError as exc:
        raise InstallSystemError(f"could not create symlink {link} -> {target}: {exc}") from exc


def create_install_root_symlink(
    link: Path,
    target: Path,
    *,
    record: Callable[[Path], None],
) -> None:
    """Create `link -> target` under `.skillpod/skills/<name>`.

    `.skillpod/skills/` is owned entirely by skillpod; any existing
    symlink there can be replaced. Refuse if it's a real directory or
    file (probably user mistake).
    """
    if link.is_symlink():
        link.unlink()
    elif link.exists():
        raise InstallConflict(
            f"refusing to overwrite non-symlink at {link} "
            f"(skillpod owns .skillpod/skills/ — remove it manually if intentional)"
        )
    _create_symlink(link, target)
    record(link)


def create_managed_fanout_symlink(
    link: Path,
    target: Path,
    project_root: Path,
    *,
    record: Callable[[Path], None],
) -> None:
    """Create an agent fan-out symlink `<.agent>/skills/<name> -> target`.

    Acceptable preconditions:
    - `link` does not exist, OR
    - `link` is already a symlink whose immediate target points into
      `.skillpod/skills/` (managed; we replace it transparently).

    Anything else (a regular file, a regular directory, or a symlink
    pointing elsewhere) raises `InstallConflict` and leaves the path
    untouched.
    """
    if link.is_symlink():
        if not is_managed_fanout(link, project_root):
            raise InstallConflict(
                f"refusing to overwrite unmanaged symlink at {link} "
                f"(target {os.readlink(link)})"
            )
        link.unlink()
    elif link.exists():
        raise InstallConflict(
            f"refusing to overwrite existing path at {link} "
            f"(skillpod only manages symlinks into .skillpod/)"
        )
    _create_symlink(link, target)
    record(link)


__all__ = [
    "create_install_root_symlink",
    "create_managed_fanout_symlink",
    "rollback_on_failure",
]
