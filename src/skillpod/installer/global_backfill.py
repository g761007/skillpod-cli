"""Reconcile the global install record with what is actually on disk.

Two jobs, both self-healing:

- **Backfill.** Skills installed before provenance was recorded have no entry.
  Their origin is recovered where possible (a symlink into the git cache still
  encodes owner/repo/commit) and recorded as ``kind: unknown`` where it is not.
  On the author's machine that is 36 of 87 skills — recording them honestly is
  what lets `skillpod global update` *report* them rather than pretend they do
  not exist.
- **Prune.** Entries whose directory has since been deleted by hand are
  dropped, so the record never claims a skill that is not there.

Sits above :mod:`skillpod.installer.global_record` because recovery needs
``profile.snapshot.recover_source``, which transitively imports the installer.
Only the CLI imports this module, so that stays acyclic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from skillpod.installer.global_record import read_global_record, write_global_record
from skillpod.installer.paths import global_install_root
from skillpod.record.models import InstallRecord, SkillRecord

if TYPE_CHECKING:
    from skillpod.profile.models import GlobalProfileSkill

_SHA1_HEX = re.compile(r"^[0-9a-f]{40}$")


@dataclass
class BackfillReport:
    recovered: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    pruned: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.recovered or self.unknown or self.pruned)


def _installed_skill_names(home: Path | None) -> set[str]:
    root = global_install_root(home)
    if not root.is_dir():
        return set()
    return {child.name for child in root.iterdir() if child.is_dir() or child.is_symlink()}


def reconcile_global_record(
    home: Path | None = None, *, persist: bool = True
) -> tuple[InstallRecord, BackfillReport]:
    """Bring the global record in line with `~/.skillpod/skills/`."""
    # Imported here rather than at module scope: recover_source lives in the
    # profile package, which imports the installer. Deferring keeps the two
    # packages importable in either order.
    from skillpod.profile.snapshot import recover_source

    record = read_global_record(home)
    on_disk = _installed_skill_names(home)
    report = BackfillReport()

    for name in sorted(on_disk - set(record.installed)):
        recovered = _recovered_entry(recover_source(name, home))
        if recovered is None:
            record.installed[name] = SkillRecord(kind="unknown")
            report.unknown.append(name)
        else:
            record.installed[name] = recovered
            report.recovered.append(name)

    for name in sorted(set(record.installed) - on_disk):
        del record.installed[name]
        report.pruned.append(name)

    if persist and report.changed:
        write_global_record(record, home)
    return record, report


def _recovered_entry(skill: GlobalProfileSkill) -> SkillRecord | None:
    """Turn a recovered source into a record entry, or None if unrecoverable.

    A cache symlink encodes the resolved commit in its path, and
    ``recover_source`` surfaces that as ``ref`` because a profile treats it as
    something to check out. A record distinguishes the two: a 40-hex value is
    the commit that was installed, not a branch that was followed.
    """
    if not skill.source:
        return None
    if _looks_local(skill.source):
        return SkillRecord(kind="local", source=skill.source)
    if skill.ref and _SHA1_HEX.fullmatch(skill.ref):
        return SkillRecord(
            kind="git", source=skill.source, commit=skill.ref, subpath=skill.subpath
        )
    # A git source we cannot tie to a commit is not something `global update`
    # can act on; recording it as git would fail the model's own invariant.
    return None


def _looks_local(source: str) -> bool:
    """True when `source` names a filesystem path rather than a git remote.

    `recover_source` returns a bare path for a symlink pointing at a local
    directory, and an ``owner/repo`` or URL for anything from the git cache.
    """
    if "://" in source or source.startswith("git@"):
        return False
    return source.startswith(("/", "~", ".")) or Path(source).is_dir()


__all__ = ["BackfillReport", "reconcile_global_record"]
