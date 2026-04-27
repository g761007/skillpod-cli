"""`skillpod list` — show installed skills, sources, and lockfile commits."""

from __future__ import annotations

from pathlib import Path

from skillpod.cli._output import emit, fail
from skillpod.installer.expand import flatten
from skillpod.installer.user_skills import discover_user_skills
from skillpod.lockfile import io as lockfile_io
from skillpod.manifest import load as load_manifest
from skillpod.manifest.models import SkillEntry


def run(*, project_root: Path, manifest_path: Path, json_output: bool) -> None:
    if not manifest_path.exists():
        raise fail(f"{manifest_path} not found", code=1, json_output=json_output)

    manifest = load_manifest(manifest_path)
    lock = lockfile_io.read(project_root / "skillfile.lock")

    skills = flatten(manifest)
    known = {skill.name for skill in skills}
    for name in discover_user_skills(project_root):
        if name not in known:
            skills.append(SkillEntry(name=name))

    rows: list[dict[str, str | None]] = []
    for skill in skills:
        locked = lock.resolved.get(skill.name)
        rows.append(
            {
                "name": skill.name,
                "source": skill.source,
                "commit": locked.commit if locked else None,
                "url": locked.url if locked else None,
            }
        )

    payload = {
        "ok": True,
        "agents": [a.name for a in manifest.agents],
        "sources": [s.model_dump() for s in manifest.sources],
        "skills": rows,
    }
    if json_output:
        emit(payload, json_output=True)
        return

    if not rows:
        emit(payload, json_output=False, human="No skills declared.")
        return

    name_w = max(8, *(len(r["name"]) for r in rows if r["name"]))
    src_w = max(8, *(len(r["source"] or "") for r in rows))
    lines = [f"{'NAME':<{name_w}}  {'SOURCE':<{src_w}}  COMMIT"]
    for r in rows:
        commit = (r["commit"] or "")[:12] if r["commit"] else "(local/unlocked)"
        lines.append(f"{r['name']:<{name_w}}  {(r['source'] or '-'):<{src_w}}  {commit}")
    emit(payload, json_output=False, human="\n".join(lines))


__all__ = ["run"]
