"""`skillpod global archive` — move scattered global skills into ~/.skillpod/skills/.

The command walks every known agent directory (`~/.<agent>/skills/<name>`),
classifies each match, and consolidates the content under
`~/.skillpod/skills/<name>` so that downstream `skillpod add` / `install`
flows can re-materialise it as a managed global skill.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from skillpod.cli._output import emit, fail
from skillpod.cli.commands.global_list import scan_global_skills
from skillpod.installer.paths import global_install_root, global_skill_dir
from skillpod.lockfile.integrity import hash_directory


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _points_into(link: Path, target_dir: Path) -> bool:
    """True if `link` is a symlink whose immediate target equals `target_dir`."""
    if not link.is_symlink():
        return False
    raw = Path(os.readlink(link))
    immediate = raw if raw.is_absolute() else (link.parent / raw)
    try:
        leaf = immediate.parent.resolve(strict=False) / immediate.name
        target = target_dir.parent.resolve(strict=False) / target_dir.name
    except OSError:
        return False
    return leaf == target


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    skill_name: str,
    json_output: bool,
    force: bool = False,
) -> None:
    matches = [Path(row["path"]) for row in scan_global_skills() if row["name"] == skill_name]
    if not matches:
        raise fail(f"global skill {skill_name!r} not found", code=1, json_output=json_output)

    blocked = [path for path in matches if _is_inside(path, project_root)]
    if blocked:
        raise fail(
            "refusing to archive project-local paths: "
            + ", ".join(str(path) for path in blocked),
            code=1,
            json_output=json_output,
        )

    dest = global_skill_dir(skill_name)

    fanout_links: list[Path] = []
    content_sources: list[Path] = []
    for path in matches:
        if _points_into(path, dest):
            fanout_links.append(path)
        else:
            content_sources.append(path)

    dest_exists = dest.is_dir()
    dest_hash: str | None = hash_directory(dest) if dest_exists else None

    source_hashes: list[tuple[Path, str]] = [
        (src, hash_directory(src)) for src in content_sources if src.is_dir()
    ]

    moved_from: list[str] = []
    removed: list[str] = []
    unlinked: list[str] = []
    skipped_existing = False

    if dest_exists:
        mismatches = [str(src) for src, h in source_hashes if h != dest_hash]
        if mismatches and not force:
            raise fail(
                f"destination {dest} exists with different content than "
                + ", ".join(mismatches)
                + "; pass --force to overwrite",
                code=1,
                json_output=json_output,
            )
        if mismatches and force:
            chosen, _ = source_hashes[0]
            assert _is_inside(dest, global_install_root())
            shutil.rmtree(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(chosen), str(dest))
            moved_from.append(str(chosen))
            for src, _ in source_hashes[1:]:
                if src.is_dir() and not src.is_symlink():
                    shutil.rmtree(src)
                else:
                    src.unlink()
                removed.append(str(src))
        else:
            skipped_existing = True
            for src, _ in source_hashes:
                if src.is_dir() and not src.is_symlink():
                    shutil.rmtree(src)
                else:
                    src.unlink()
                removed.append(str(src))
    else:
        if not source_hashes:
            raise fail(
                f"global skill {skill_name!r} has no concrete content under any "
                "agent directory (only stale symlinks); nothing to archive",
                code=1,
                json_output=json_output,
            )
        first_hash = source_hashes[0][1]
        diverged = [str(src) for src, h in source_hashes[1:] if h != first_hash]
        if diverged and not force:
            chosen = source_hashes[0][0]
            raise fail(
                f"multiple agent copies of {skill_name!r} have different content; "
                f"pass --force to use {chosen} (diverging: " + ", ".join(diverged) + ")",
                code=1,
                json_output=json_output,
            )
        chosen, _ = source_hashes[0]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(chosen), str(dest))
        moved_from.append(str(chosen))
        for src, _ in source_hashes[1:]:
            if src.is_dir() and not src.is_symlink():
                shutil.rmtree(src)
            else:
                src.unlink()
            removed.append(str(src))

    for link in fanout_links:
        link.unlink()
        unlinked.append(str(link))

    payload = {
        "ok": True,
        "name": skill_name,
        "dest": str(dest),
        "moved_from": moved_from,
        "removed": removed,
        "unlinked": unlinked,
        "skipped_existing": skipped_existing,
    }
    if json_output:
        emit(payload, json_output=True)
        return

    lines: list[str] = []
    if skipped_existing:
        lines.append(f"Destination already up to date: {dest}")
    else:
        for moved in moved_from:
            lines.append(f"Moved {moved} -> {dest}")
    for gone in removed:
        lines.append(f"Removed agent copy: {gone}")
    for stale in unlinked:
        lines.append(f"Unlinked stale fan-out: {stale}")
    if not lines:
        lines.append(f"Nothing to do for {skill_name!r}.")
    emit(payload, json_output=False, human="\n".join(lines))


__all__ = ["run"]
