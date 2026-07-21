"""One-way migration from a legacy `skillfile.lock` to an install record.

Runs once, lazily, the first time a project with a lockfile but no record is
installed. Reading the old file directly (rather than keeping the retired
lockfile models around) keeps the dead schema out of the codebase — this
module is the only thing that still knows the shape.

`skillfile.lock` is **never deleted**. It is a committed file the user owns;
the CLI says what to do with it and leaves the decision alone.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from skillpod.record.models import InstallRecord, SkillRecord

LEGACY_LOCKFILE = "skillfile.lock"

_SHA1_HEX = re.compile(r"^[0-9a-f]{40}$")
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def legacy_lockfile_path(project_root: Path) -> Path:
    return project_root / LEGACY_LOCKFILE


def migrate_lockfile(project_root: Path) -> InstallRecord | None:
    """Return an `InstallRecord` seeded from `skillfile.lock`, or None.

    None means there is nothing to migrate — no lockfile, or one that cannot
    be parsed. A malformed legacy file is not worth failing an install over:
    the record is rebuilt from scratch on the next resolve anyway.

    Lockfile entries carried no ``ref``, so the resulting records have none.
    That is honest — the old format genuinely did not record which branch was
    followed — and `skillpod update` falls back to the manifest's ref.
    """
    path = legacy_lockfile_path(project_root)
    if not path.is_file():
        return None

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return None
    if not isinstance(data, dict):
        return None

    resolved = data.get("resolved")
    if not isinstance(resolved, dict):
        return None

    installed: dict[str, SkillRecord] = {}
    for name, entry in resolved.items():
        if not isinstance(name, str) or not isinstance(entry, dict):
            continue
        url, commit, sha256 = entry.get("url"), entry.get("commit"), entry.get("sha256")
        if not isinstance(url, str) or not isinstance(commit, str):
            continue
        if not _SHA1_HEX.fullmatch(commit):
            continue
        if not (isinstance(sha256, str) and _SHA256_HEX.fullmatch(sha256)):
            sha256 = None
        installed[name] = SkillRecord(
            kind="git", source=url, commit=commit, sha256=sha256
        )

    return InstallRecord(installed=installed) if installed else None


__all__ = ["LEGACY_LOCKFILE", "legacy_lockfile_path", "migrate_lockfile"]
