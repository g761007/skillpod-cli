"""Symlink creation, mode-aware materialisation, rollback + safety checks.

``create_install_root_symlink`` and ``create_managed_fanout_symlink`` are kept
for backward-compat; new code should use ``materialise_fanout``.

``create_install_root_symlink`` is always symlink-only — ``.skillpod/skills/<name>/``
is always a symlink to the source location regardless of ``install.mode``.
The ``install.mode`` only governs the fan-out side.
"""

from __future__ import annotations

import logging
import os
import warnings
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

from skillpod.installer.adapter import Adapter, InstallMode
from skillpod.installer.errors import InstallConflict, InstallSystemError
from skillpod.installer.paths import is_managed_fanout

logger = logging.getLogger(__name__)


@contextmanager
def rollback_on_failure() -> Iterator[Callable[[Path], None]]:
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
                        import shutil

                        with suppress(OSError):
                            shutil.rmtree(path, ignore_errors=True)
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
    """Create ``link -> target`` under ``.skillpod/skills/<name>``.

    ``.skillpod/skills/`` is owned entirely by skillpod; any existing
    symlink there can be replaced. Refuse if it's a real directory or
    file (probably user mistake).

    This function is always symlink-only — the install root is never
    materialised as a copy or hardlink tree.  Only the agent fan-out
    side is governed by ``install.mode``.
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
    """Create an agent fan-out symlink ``<.agent>/skills/<name> -> target``.

    Acceptable preconditions:
    - ``link`` does not exist, OR
    - ``link`` is already a symlink whose immediate target points into
      ``.skillpod/skills/`` (managed; we replace it transparently).

    Anything else (a regular file, a regular directory, or a symlink
    pointing elsewhere) raises ``InstallConflict`` and leaves the path
    untouched.

    .. note::
        This is the legacy symlink-only helper kept for backward compatibility.
        New call sites should use ``materialise_fanout`` instead.
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


def materialise_fanout(
    *,
    skill_name: str,
    source_dir: Path,
    target_dir: Path,
    agent: str,
    project_root: Path,
    mode: InstallMode,
    fallback: list[str],
    adapter: Adapter,
    record: Callable[[Path], None],
) -> None:
    """Materialise one ``(agent, skill)`` fan-out entry via the registered adapter.

    Handles:
    - Pre-existing managed symlinks are removed before calling the adapter.
    - Cross-FS device check for ``hardlink`` mode (downgrades to ``copy``
      with a warning).
    - ``symlink`` failure fallback chain: iterates ``fallback`` list, warns
      once on success, raises ``InstallSystemError`` if all modes are
      exhausted.
    - Delegates actual materialisation to ``adapter.adapt()``.
    """
    # --- Tidy up any previous managed symlink ---
    if target_dir.is_symlink():
        if not is_managed_fanout(target_dir, project_root):
            raise InstallConflict(
                f"refusing to overwrite unmanaged symlink at {target_dir} "
                f"(target {os.readlink(target_dir)})"
            )
        target_dir.unlink()
    elif target_dir.exists():
        raise InstallConflict(
            f"refusing to overwrite existing path at {target_dir} "
            f"(skillpod only manages entries into .skillpod/)"
        )

    target_dir.parent.mkdir(parents=True, exist_ok=True)

    # --- Cross-FS probe for hardlink mode ---
    effective_mode = _resolve_mode(mode, source_dir, target_dir, skill_name, agent)

    # --- Attempt materialisation with fallback ---
    _attempt_with_fallback(
        skill_name=skill_name,
        source_dir=source_dir,
        target_dir=target_dir,
        agent=agent,
        effective_mode=effective_mode,
        fallback=fallback,
        adapter=adapter,
        record=record,
    )


def _resolve_mode(
    mode: InstallMode,
    source_dir: Path,
    target_dir: Path,
    skill_name: str,
    agent: str,
) -> InstallMode:
    """Downgrade hardlink to copy if source and target are on different devices."""
    if mode is not InstallMode.HARDLINK:
        return mode
    try:
        src_dev = os.stat(source_dir).st_dev
        dst_dev = os.stat(target_dir.parent).st_dev
    except OSError:
        # If we can't stat, fall back to copy to be safe.
        warnings.warn(
            f"skillpod: could not probe filesystem devices for hardlink "
            f"(skill={skill_name!r}, agent={agent!r}); falling back to copy",
            UserWarning,
            stacklevel=4,
        )
        return InstallMode.COPY

    if src_dev != dst_dev:
        warnings.warn(
            f"skillpod: source and target are on different filesystems — "
            f"hardlink mode is not possible for skill={skill_name!r}, "
            f"agent={agent!r}; falling back to copy",
            UserWarning,
            stacklevel=4,
        )
        return InstallMode.COPY
    return mode


def _attempt_with_fallback(
    *,
    skill_name: str,
    source_dir: Path,
    target_dir: Path,
    agent: str,
    effective_mode: InstallMode,
    fallback: list[str],
    adapter: Adapter,
    record: Callable[[Path], None],
) -> None:
    """Try ``effective_mode``; on OSError iterate ``fallback`` list."""
    # For non-symlink modes there is no OS-level failure to catch from the
    # adapter call itself (copy/hardlink OSErrors bubble up as system errors).
    # The fallback chain only applies when the *initial* symlink attempt fails.
    if effective_mode is not InstallMode.SYMLINK:
        adapter.adapt(
            skill_name=skill_name,
            source_dir=source_dir,
            target_dir=target_dir,
            mode=effective_mode,
        )
        record(target_dir)
        return

    # Symlink mode: attempt, then iterate fallback on OSError.
    try:
        adapter.adapt(
            skill_name=skill_name,
            source_dir=source_dir,
            target_dir=target_dir,
            mode=InstallMode.SYMLINK,
        )
        record(target_dir)
        return
    except OSError as sym_exc:
        logger.debug(
            "symlink failed for skill=%s agent=%s: %s — trying fallback",
            skill_name,
            agent,
            sym_exc,
        )

    for fb_mode_str in fallback:
        fb_mode = InstallMode(fb_mode_str)
        # Clean up any partial target from the failed symlink attempt.
        with suppress(OSError):
            if target_dir.is_symlink() or target_dir.exists():
                target_dir.unlink(missing_ok=True)
        try:
            adapter.adapt(
                skill_name=skill_name,
                source_dir=source_dir,
                target_dir=target_dir,
                mode=fb_mode,
            )
            warnings.warn(
                f"skillpod: symlink failed for skill={skill_name!r}, "
                f"agent={agent!r}; fell back to mode={fb_mode_str!r}",
                UserWarning,
                stacklevel=5,
            )
            record(target_dir)
            return
        except OSError:
            continue

    raise InstallSystemError(
        f"could not materialise skill={skill_name!r} for agent={agent!r}: "
        f"symlink failed and fallback list {fallback!r} is empty or all failed"
    )


__all__ = [
    "create_install_root_symlink",
    "create_managed_fanout_symlink",
    "materialise_fanout",
    "rollback_on_failure",
]
