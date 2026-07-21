"""`skillpod list` — show declared skills and what is actually installed."""

from __future__ import annotations

from pathlib import Path

from skillpod.cli._output import emit, fail
from skillpod.installer.expand import flatten
from skillpod.installer.paths import project_record_path
from skillpod.installer.user_skills import discover_user_skills
from skillpod.manifest import load as load_manifest
from skillpod.manifest.models import SkillEntry
from skillpod.record import io as record_io
from skillpod.skillset.inventory import take_inventory


def run(*, project_root: Path, manifest_path: Path, json_output: bool) -> None:
    if not manifest_path.exists():
        raise fail(f"{manifest_path} not found", code=1, json_output=json_output)

    manifest = load_manifest(manifest_path)
    installed = record_io.read(project_record_path(project_root)).installed

    skills = flatten(manifest)
    known = {skill.name for skill in skills}
    for name in discover_user_skills(project_root):
        if name not in known:
            skills.append(SkillEntry(name=name))

    # Shared with `status` so the two cannot disagree about the same skill.
    states = {s.name: s.state for s in take_inventory(manifest, project_root).skills}
    rows: list[dict[str, str | None]] = []
    for skill in skills:
        rec = installed.get(skill.name)
        layer = str(states.get(skill.name, "missing"))
        rows.append(
            {
                "name": skill.name,
                "source": skill.source,
                "layer": layer,
                "kind": rec.kind if rec else None,
                "commit": rec.commit if rec else None,
                "url": rec.source if rec else None,
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
    lines = [f"{'NAME':<{name_w}}  {'SOURCE':<{src_w}}  {'LAYER':<8}  INSTALLED"]
    for r in rows:
        if r["commit"]:
            state = r["commit"][:12]
        elif r["layer"] == "global":
            state = "(from ~/.skillpod)"
        elif r["kind"] == "local":
            state = "(local)"
        elif r["kind"]:
            state = f"({r['kind']})"
        else:
            state = "(not installed)"
        lines.append(
            f"{r['name']:<{name_w}}  {(r['source'] or '-'):<{src_w}}  "
            f"{r['layer']:<8}  {state}"
        )
    emit(payload, json_output=False, human="\n".join(lines))


__all__ = ["run"]
