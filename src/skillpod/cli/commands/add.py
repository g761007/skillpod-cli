"""`skillpod add <skill>` — append a skill to skillfile.yml and install it.

Atomicity: snapshot the manifest text before mutation; if the install
pipeline fails we restore the original text so the manifest tracks the
filesystem.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from skillpod.cli._output import emit, fail, run_with_exit_codes
from skillpod.installer import install
from skillpod.manifest import load as load_manifest


def _append_skill_to_manifest(manifest_path: Path, skill_name: str) -> None:
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("manifest top level must be a mapping")
    skills = raw.get("skills") or []
    skills.append(skill_name)
    raw["skills"] = skills
    manifest_path.write_text(
        yaml.safe_dump(raw, sort_keys=False, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    skill_name: str,
    json_output: bool,
) -> None:
    if not manifest_path.exists():
        raise fail(
            f"{manifest_path} not found — run `skillpod init` first",
            code=1,
            json_output=json_output,
        )

    existing = load_manifest(manifest_path)
    if any(s.name == skill_name for s in existing.skills):
        raise fail(
            f"skill {skill_name!r} is already in {manifest_path}",
            code=1,
            json_output=json_output,
        )

    snapshot = manifest_path.read_text(encoding="utf-8")
    try:
        _append_skill_to_manifest(manifest_path, skill_name)
        report = run_with_exit_codes(
            lambda: install(project_root, manifest_path=manifest_path),
            json_output=json_output,
        )
    except BaseException:
        manifest_path.write_text(snapshot, encoding="utf-8")
        raise

    added = next((s for s in report.installed if s.name == skill_name), None)
    if added is None:  # pragma: no cover - install would have raised
        raise fail(
            f"skill {skill_name!r} did not appear in install report",
            code=2,
            json_output=json_output,
        )

    payload = {
        "ok": True,
        "added": skill_name,
        "source": added.resolved.source_kind,
        "commit": added.resolved.commit,
    }
    human = f"Added {skill_name} ({added.resolved.source_kind})"
    if added.resolved.commit:
        human += f" at {added.resolved.commit[:8]}"
    emit(payload, json_output=json_output, human=human)


__all__ = ["run"]
