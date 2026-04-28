"""`skillpod add` — install one or more skills.

Two dispatch modes, decided by the positional argument:

1. **bare skill name** (legacy): append the name to ``skills:`` and run
   the install pipeline against declared sources / registry.
2. **source identifier** (git URL / ``owner/repo`` / local path): fetch
   the source, list its skills (``-l``) or install the selected subset
   either into the project (auto-adding a ``sources:`` entry to
   ``skillfile.yml``) or into ``~/.skillpod/skills/`` with fan-out
   (``-g``).

Atomicity for project-mode: snapshot the manifest text before mutation;
if any subsequent step raises, restore the original text so the
manifest tracks the filesystem.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer
import yaml

from skillpod.cli._output import emit, fail, run_with_exit_codes
from skillpod.installer import install
from skillpod.installer.global_install import (
    DEFAULT_GLOBAL_AGENTS,
    install_global,
)
from skillpod.manifest import load as load_manifest
from skillpod.manifest.models import SUPPORTED_AGENTS
from skillpod.sources.discovery import DiscoveredSkill, discover_skills
from skillpod.sources.git import populate_cache, resolve_ref
from skillpod.sources.spec import SourceSpec, derive_unique_name, parse_source_spec

# ---------------------------------------------------------------------------
# Legacy bare-name path (preserves 0.5.x behaviour)
# ---------------------------------------------------------------------------


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


def _run_legacy_add(
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


# ---------------------------------------------------------------------------
# Source-mode helpers
# ---------------------------------------------------------------------------


def _fetch_source(spec: SourceSpec) -> tuple[Path, str]:
    """Materialise the source on disk and return `(root, commit_or_empty)`."""
    if spec.kind == "git":
        commit = resolve_ref(spec.url_or_path, spec.ref)
        root = populate_cache(spec.url_or_path, commit)
        return root, commit
    root = Path(spec.url_or_path).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"local source path does not exist: {root}")
    return root, ""


def _select_skills(
    discovered: list[DiscoveredSkill],
    requested: list[str] | None,
    *,
    yes: bool,
    json_output: bool,
) -> list[DiscoveredSkill]:
    """Filter `discovered` down to the user's selection.

    Behaviour:
    - `requested == ['*']` or no flag with `yes=True`: install all
    - explicit names: filter by name (error on unknown)
    - no flag, no `-y`, interactive TTY: prompt with comma-separated indices
    - no flag, no `-y`, non-TTY: install all (CI-friendly)
    """
    if not discovered:
        return []

    if requested is None or len(requested) == 0:
        if yes or not sys.stdin.isatty() or json_output:
            return list(discovered)
        return _interactive_pick(discovered)

    if len(requested) == 1 and requested[0] == "*":
        return list(discovered)

    by_name = {s.name: s for s in discovered}
    selected: list[DiscoveredSkill] = []
    missing: list[str] = []
    for name in requested:
        skill = by_name.get(name)
        if skill is None:
            missing.append(name)
        else:
            selected.append(skill)
    if missing:
        available = ", ".join(s.name for s in discovered)
        raise ValueError(
            f"skill(s) not found in source: {', '.join(missing)} "
            f"(available: {available})"
        )
    return selected


def _interactive_pick(discovered: list[DiscoveredSkill]) -> list[DiscoveredSkill]:
    typer.echo("Available skills:")
    typer.echo("  0) all")
    for idx, skill in enumerate(discovered, start=1):
        suffix = f" — {skill.description}" if skill.description else ""
        typer.echo(f"  {idx}) {skill.name}{suffix}")
    raw = typer.prompt("Select (comma-separated indices, or 0 for all)").strip()
    if not raw or raw == "0":
        return list(discovered)
    picked: list[DiscoveredSkill] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            i = int(token)
        except ValueError as exc:
            raise ValueError(f"not a number: {token!r}") from exc
        if i == 0:
            return list(discovered)
        if not 1 <= i <= len(discovered):
            raise ValueError(f"index out of range: {i}")
        picked.append(discovered[i - 1])
    return picked


def _print_listing(
    spec: SourceSpec,
    discovered: list[DiscoveredSkill],
    *,
    json_output: bool,
) -> None:
    if json_output:
        payload = {
            "ok": True,
            "source": {
                "kind": spec.kind,
                "url_or_path": spec.url_or_path,
                "ref": spec.ref,
            },
            "skills": [
                {"name": s.name, "description": s.description, "rel_path": s.rel_path}
                for s in discovered
            ],
        }
        emit(payload, json_output=True)
        return

    if not discovered:
        emit(
            {"ok": True, "skills": []},
            json_output=False,
            human=f"No SKILL.md found under {spec.url_or_path}",
        )
        return

    name_w = max(4, *(len(s.name) for s in discovered))
    lines = [f"{'NAME':<{name_w}}  DESCRIPTION"]
    for skill in discovered:
        lines.append(f"{skill.name:<{name_w}}  {skill.description}")
    emit(
        {"ok": True, "skills": [s.name for s in discovered]},
        json_output=False,
        human="\n".join(lines),
    )


# ---------------------------------------------------------------------------
# Project-mode source install
# ---------------------------------------------------------------------------


def _normalise_agent_filter(
    agent_filter: list[str] | None,
    *,
    declared_agents: list[str],
) -> list[str] | None:
    """Validate `-a` against manifest agents; return None when no filter."""
    if not agent_filter:
        return None
    unknown = [a for a in agent_filter if a not in declared_agents]
    if unknown:
        raise ValueError(
            f"agent(s) {', '.join(unknown)} not declared in manifest "
            f"(declared: {', '.join(declared_agents) or '<none>'})"
        )
    return list(dict.fromkeys(agent_filter))  # de-dup, preserve order


def _ensure_source_and_skills(
    manifest_path: Path,
    spec: SourceSpec,
    selected: list[DiscoveredSkill],
    *,
    source_name_override: str | None,
) -> tuple[str, list[str], list[str]]:
    """Add a `sources:` entry if missing, then add each selected skill.

    Returns `(source_name, added_skill_names, skipped_skill_names)`.
    `skipped` covers skills that were already declared in the manifest
    (left untouched, not an error).
    """
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("manifest top level must be a mapping")

    sources_list = list(raw.get("sources") or [])
    skills_list = list(raw.get("skills") or [])

    existing_source_names = {
        entry["name"]
        for entry in sources_list
        if isinstance(entry, dict) and "name" in entry
    }

    # Reuse an existing source entry whose URL/path matches what we'd add.
    matching = _find_matching_source(sources_list, spec)
    if matching is not None:
        source_name = matching
    else:
        base_name = source_name_override or spec.derived_name
        source_name = derive_unique_name(base_name, existing_source_names)
        new_source: dict[str, object] = {"name": source_name, "type": spec.kind}
        if spec.kind == "git":
            new_source["url"] = spec.url_or_path
            new_source["ref"] = spec.ref
        else:
            new_source["path"] = spec.url_or_path
        new_source["priority"] = 50
        sources_list.append(new_source)

    existing_skill_names: set[str] = set()
    for entry in skills_list:
        if isinstance(entry, str):
            existing_skill_names.add(entry)
        elif isinstance(entry, dict) and "name" in entry:
            existing_skill_names.add(entry["name"])

    added: list[str] = []
    skipped: list[str] = []
    for skill in selected:
        if skill.name in existing_skill_names:
            skipped.append(skill.name)
            continue
        skills_list.append({"name": skill.name, "source": source_name})
        added.append(skill.name)

    raw["sources"] = sources_list
    raw["skills"] = skills_list
    manifest_path.write_text(
        yaml.safe_dump(raw, sort_keys=False, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    return source_name, added, skipped


def _find_matching_source(sources_list: list[object], spec: SourceSpec) -> str | None:
    """Return the name of an existing source that already covers `spec`."""
    for entry in sources_list:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != spec.kind:
            continue
        if spec.kind == "git" and entry.get("url") == spec.url_or_path:
            return entry.get("name") if isinstance(entry.get("name"), str) else None
        if spec.kind == "local" and entry.get("path") == spec.url_or_path:
            return entry.get("name") if isinstance(entry.get("name"), str) else None
    return None


def _run_source_project(
    *,
    project_root: Path,
    manifest_path: Path,
    spec: SourceSpec,
    selected: list[DiscoveredSkill],
    agent_filter: list[str] | None,
    source_name_override: str | None,
    json_output: bool,
) -> None:
    if not manifest_path.exists():
        raise fail(
            f"{manifest_path} not found — run `skillpod init` first",
            code=1,
            json_output=json_output,
        )

    existing = load_manifest(manifest_path)
    declared_agents = [a.name for a in existing.agents]
    try:
        normalised_filter = _normalise_agent_filter(
            agent_filter, declared_agents=declared_agents
        )
    except ValueError as exc:
        raise fail(str(exc), code=1, json_output=json_output) from exc

    snapshot = manifest_path.read_text(encoding="utf-8")
    try:
        source_name, added, skipped = _ensure_source_and_skills(
            manifest_path,
            spec,
            selected,
            source_name_override=source_name_override,
        )
        report = run_with_exit_codes(
            lambda: install(
                project_root,
                manifest_path=manifest_path,
                agent_filter=normalised_filter,
            ),
            json_output=json_output,
        )
    except BaseException:
        manifest_path.write_text(snapshot, encoding="utf-8")
        raise

    installed_by_name = {s.name: s for s in report.installed}
    payload_skills = []
    for name in added:
        entry = installed_by_name.get(name)
        payload_skills.append(
            {
                "name": name,
                "source_kind": entry.resolved.source_kind if entry else None,
                "commit": entry.resolved.commit if entry else None,
            }
        )

    payload = {
        "ok": True,
        "source": source_name,
        "added": added,
        "skipped": skipped,
        "skills": payload_skills,
        "fanned_out_to": report.fanned_out_to,
    }
    human_lines = [
        f"Source {source_name!r} → added {len(added)} skill(s): "
        f"{', '.join(added) if added else '(none)'}"
    ]
    if skipped:
        human_lines.append(f"Skipped (already in manifest): {', '.join(skipped)}")
    if report.fanned_out_to:
        human_lines.append(f"Fanned out to: {', '.join(report.fanned_out_to)}")
    emit(payload, json_output=json_output, human="\n".join(human_lines))


# ---------------------------------------------------------------------------
# Global-mode source install
# ---------------------------------------------------------------------------


def _resolve_global_agents(agents: list[str] | None) -> list[str]:
    """Validate `-a` for global mode; default to all known agents."""
    if not agents:
        return list(DEFAULT_GLOBAL_AGENTS)
    unknown = [a for a in agents if a not in SUPPORTED_AGENTS]
    if unknown:
        raise ValueError(
            f"unknown agent(s): {', '.join(unknown)} "
            f"(supported: {', '.join(SUPPORTED_AGENTS)})"
        )
    return list(dict.fromkeys(agents))


def _run_source_global(
    *,
    spec: SourceSpec,
    selected: list[DiscoveredSkill],
    agents: list[str] | None,
    yes: bool,
    json_output: bool,
) -> None:
    try:
        target_agents = _resolve_global_agents(agents)
    except ValueError as exc:
        raise fail(str(exc), code=1, json_output=json_output) from exc

    report = run_with_exit_codes(
        lambda: install_global(
            spec,
            selected,
            agents=target_agents,
            force=yes,
        ),
        json_output=json_output,
    )

    payload = {
        "ok": True,
        "scope": "global",
        "source": {
            "kind": spec.kind,
            "url_or_path": spec.url_or_path,
            "ref": spec.ref,
        },
        "install_root": str(report.install_root),
        "skills": [
            {
                "name": s.name,
                "install_path": str(s.install_path),
                "fanned_out_to": s.fanned_out_to,
                "commit": s.resolved.commit,
            }
            for s in report.installed
        ],
    }
    human_lines = [
        f"Installed {len(report.installed)} skill(s) globally to {report.install_root}",
    ]
    for entry in report.installed:
        human_lines.append(
            f"  {entry.name} → {entry.install_path} "
            f"(fan-out: {', '.join(entry.fanned_out_to) or '<none>'})"
        )
    emit(payload, json_output=json_output, human="\n".join(human_lines))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    target: str,
    skills: list[str] | None,
    agents: list[str] | None,
    list_only: bool,
    global_install: bool,
    yes: bool,
    ref: str,
    source_name: str | None,
    json_output: bool,
) -> None:
    spec = parse_source_spec(target, ref=ref)

    # ---- Bare skill name (legacy) ----------------------------------------
    if spec is None:
        if list_only or skills or global_install or source_name:
            raise fail(
                "flags --list/--skill/--global/--source-name require a source argument "
                "(git URL, owner/repo, or local path), not a bare skill name",
                code=1,
                json_output=json_output,
            )
        if agents:
            raise fail(
                "--agent is only valid for source-mode add (positional must be a source)",
                code=1,
                json_output=json_output,
            )
        _run_legacy_add(
            project_root=project_root,
            manifest_path=manifest_path,
            skill_name=target,
            json_output=json_output,
        )
        return

    # ---- Source-mode -----------------------------------------------------
    try:
        root, _commit = _fetch_source(spec)
    except FileNotFoundError as exc:
        raise fail(str(exc), code=1, json_output=json_output) from exc

    discovered = discover_skills(root)

    if list_only:
        _print_listing(spec, discovered, json_output=json_output)
        return

    if not discovered:
        raise fail(
            f"no SKILL.md found under {spec.url_or_path}",
            code=1,
            json_output=json_output,
        )

    try:
        selected = _select_skills(
            discovered, skills, yes=yes, json_output=json_output
        )
    except ValueError as exc:
        raise fail(str(exc), code=1, json_output=json_output) from exc
    if not selected:
        raise fail("no skills selected", code=1, json_output=json_output)

    if global_install:
        _run_source_global(
            spec=spec,
            selected=selected,
            agents=agents,
            yes=yes,
            json_output=json_output,
        )
        return

    _run_source_project(
        project_root=project_root,
        manifest_path=manifest_path,
        spec=spec,
        selected=selected,
        agent_filter=agents,
        source_name_override=source_name,
        json_output=json_output,
    )


__all__ = ["run"]
