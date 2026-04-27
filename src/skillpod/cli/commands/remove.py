"""`skillpod remove <skill>` — drop a skill and its materialised state."""

from __future__ import annotations

from pathlib import Path

import yaml

from skillpod.cli._output import emit, fail
from skillpod.installer import uninstall
from skillpod.lockfile import io as lockfile_io
from skillpod.manifest import load as load_manifest


def _drop_skill_from_manifest(manifest_path: Path, skill_name: str) -> bool:
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("manifest top level must be a mapping")
    skills = raw.get("skills") or []
    new_skills = []
    dropped = False
    for entry in skills:
        if isinstance(entry, str) and entry == skill_name:
            dropped = True
            continue
        if isinstance(entry, dict) and entry.get("name") == skill_name:
            dropped = True
            continue
        new_skills.append(entry)
    raw["skills"] = new_skills
    if dropped:
        manifest_path.write_text(
            yaml.safe_dump(
                raw, sort_keys=False, default_flow_style=False, allow_unicode=True
            ),
            encoding="utf-8",
        )
    return dropped


def _drop_lockfile_entry(lockfile_path: Path, skill_name: str) -> None:
    lock = lockfile_io.read(lockfile_path)
    if skill_name in lock.resolved:
        del lock.resolved[skill_name]
        lockfile_io.write(lockfile_path, lock)


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    skill_name: str,
    json_output: bool,
) -> None:
    if not manifest_path.exists():
        raise fail(f"{manifest_path} not found", code=1, json_output=json_output)

    manifest = load_manifest(manifest_path)
    if not any(s.name == skill_name for s in manifest.skills):
        raise fail(
            f"skill {skill_name!r} is not declared in {manifest_path}",
            code=1,
            json_output=json_output,
        )

    snapshot = manifest_path.read_text(encoding="utf-8")
    try:
        _drop_skill_from_manifest(manifest_path, skill_name)
        uninstall(project_root, skill_name, manifest_path=manifest_path)
        _drop_lockfile_entry(project_root / "skillfile.lock", skill_name)
    except BaseException:
        manifest_path.write_text(snapshot, encoding="utf-8")
        raise

    payload = {"ok": True, "removed": skill_name}
    emit(payload, json_output=json_output, human=f"Removed {skill_name}")


__all__ = ["run"]
