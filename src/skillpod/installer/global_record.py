"""The install record for the global scope (`~/.skillpod/installed.yml`).

Deliberately thin and dependency-free. `global_install` sits at the bottom of
the import graph, so anything it imports must not reach back to it — that rules
out putting provenance *recovery* here, since recovery needs
`profile.snapshot.recover_source`, which transitively imports the installer.
Recovery therefore lives in :mod:`skillpod.installer.global_backfill`, above
this module and imported only by the CLI.
"""

from __future__ import annotations

from pathlib import Path

from skillpod.installer.paths import global_record_path
from skillpod.record import io as record_io
from skillpod.record.models import InstallRecord, SkillKind, SkillRecord


def read_global_record(home: Path | None = None) -> InstallRecord:
    return record_io.read(global_record_path(home))


def write_global_record(record: InstallRecord, home: Path | None = None) -> None:
    record_io.write(global_record_path(home), record)


def record_global_installs(
    entries: dict[str, SkillRecord], home: Path | None = None
) -> None:
    """Merge `entries` into the global record, leaving other skills alone.

    A global install only ever concerns the skills it just materialised; every
    other entry describes something still on disk and must survive.
    """
    if not entries:
        return
    record = read_global_record(home)
    record.installed.update(entries)
    write_global_record(record, home)


def drop_global_record(skill_name: str, home: Path | None = None) -> None:
    """Forget `skill_name`, if the record mentions it."""
    record = read_global_record(home)
    if skill_name in record.installed:
        del record.installed[skill_name]
        write_global_record(record, home)


def build_record_entry(
    *,
    kind: SkillKind,
    source: str | None,
    ref: str | None,
    commit: str | None,
    subpath: str | None,
    sha256: str | None,
) -> SkillRecord:
    """Assemble one entry, normalising the fields a kind must not carry."""
    if kind == "local":
        return SkillRecord(kind="local", source=source, subpath=subpath, sha256=sha256)
    return SkillRecord(
        kind=kind,
        source=source,
        ref=ref,
        commit=commit,
        subpath=subpath,
        sha256=sha256,
    )


__all__ = [
    "build_record_entry",
    "drop_global_record",
    "read_global_record",
    "record_global_installs",
    "write_global_record",
]
