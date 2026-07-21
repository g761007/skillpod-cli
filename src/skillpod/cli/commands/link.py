"""`skillpod link` / `skillpod unlink` — attach or detach a skill from agents.

Project scope by default, `-g` for global. The two scopes previously had
different verbs — `add`/`remove` for a project, `link`/`unlink` for global —
which meant learning two vocabularies for one mental action. `global link`
and `global unlink` remain as aliases.
"""

from __future__ import annotations

from pathlib import Path

from skillpod.cli._output import emit, fail, run_with_exit_codes
from skillpod.cli.commands import global_link, global_unlink
from skillpod.installer.project_link import link_skill, unlink_skill
from skillpod.manifest import load as load_manifest


def _manifest_or_fail(manifest_path: Path, *, json_output: bool):  # type: ignore[no-untyped-def]
    if not manifest_path.exists():
        raise fail(
            f"{manifest_path} not found — use `-g` to link a global skill, "
            f"or run `skillpod init` first",
            code=1,
            json_output=json_output,
        )
    return load_manifest(manifest_path)


def run_link(
    *,
    project_root: Path,
    manifest_path: Path,
    skill_name: str,
    agents: list[str] | None,
    is_global: bool,
    yes: bool,
    json_output: bool,
) -> None:
    if is_global:
        global_link.run(
            project_root=project_root,
            manifest_path=manifest_path,
            skill_name=skill_name,
            agents=agents,
            yes=yes,
            json_output=json_output,
        )
        return

    manifest = _manifest_or_fail(manifest_path, json_output=json_output)

    def _run() -> None:
        report = link_skill(project_root, manifest, skill_name, agents=agents)
        payload = {
            "ok": True,
            "scope": "project",
            "name": report.name,
            "linked": report.linked,
            "already_linked": report.already_linked,
            "copied_from_global": report.copied_from_global,
        }
        lines: list[str] = []
        if report.copied_from_global:
            lines.append(
                f"Copied {report.name!r} from ~/.skillpod/skills/ — nothing downloaded."
            )
        if report.linked:
            lines.append(f"Linked to: {', '.join(report.linked)}")
        if report.already_linked:
            lines.append(f"Already linked: {', '.join(report.already_linked)}")
        if not lines:
            lines.append(f"Nothing to do for {report.name!r}.")
        emit(payload, json_output=json_output, human="\n".join(lines))

    run_with_exit_codes(_run, json_output=json_output)


def run_unlink(
    *,
    project_root: Path,
    manifest_path: Path,
    skill_name: str,
    agents: list[str] | None,
    is_global: bool,
    json_output: bool,
) -> None:
    if is_global:
        global_unlink.run(
            project_root=project_root,
            manifest_path=manifest_path,
            skill_name=skill_name,
            agents=agents,
            json_output=json_output,
        )
        return

    manifest = _manifest_or_fail(manifest_path, json_output=json_output)

    def _run() -> None:
        report = unlink_skill(project_root, manifest, skill_name, agents=agents)
        payload = {
            "ok": True,
            "scope": "project",
            "name": report.name,
            "unlinked": report.unlinked,
            "not_linked": report.not_linked,
            "skipped_unmanaged": report.skipped_unmanaged,
        }
        lines: list[str] = []
        if report.unlinked:
            lines.append(f"Unlinked from: {', '.join(report.unlinked)}")
            lines.append(
                f"The copy stays in .skillpod/skills/{report.name}, so "
                f"`skillpod link {report.name}` needs no download."
            )
        for agent in report.skipped_unmanaged:
            lines.append(
                f"Skipped {agent}: the entry there was not created by skillpod"
            )
        if not lines:
            lines.append(f"{report.name!r} was not linked to any agent.")
        emit(payload, json_output=json_output, human="\n".join(lines))

    run_with_exit_codes(_run, json_output=json_output)


__all__ = ["run_link", "run_unlink"]
