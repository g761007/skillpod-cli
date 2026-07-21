"""`skillpod doctor` — verify manifest/record/symlink consistency.

Checks performed (in order):
1. Every skill the manifest recommends is installed (warning if not — a
   recommendation the developer has not acted on is not a broken state).
2. Every skill in the install record still has its materialised directory at
   .skillpod/skills/<name>/ (error — record and disk disagree).
3. Every .<agent>/skills/<name> symlink declared by the manifest resolves into
   .skillpod/skills/.
4. No directory under .skillpod/skills/ is absent from the manifest (orphan).

Exit codes:
    0  no error-severity findings (warnings OK)
    1  one or more error-severity findings
    2  filesystem unreadable / manifest missing
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

import yaml

from skillpod.cli._output import emit, fail
from skillpod.installer.expand import flatten
from skillpod.installer.paths import (
    agent_skill_dir,
    global_skill_dir,
    install_root,
    is_managed_fanout,
    project_record_path,
)
from skillpod.installer.user_skills import discover_user_skills
from skillpod.manifest import load as load_manifest
from skillpod.manifest.models import SkillEntry, Skillfile
from skillpod.record import io as record_io


class Finding(TypedDict, total=False):
    severity: str  # "error" | "warning"
    code: str
    message: str
    path: str


class SchemaHint(TypedDict):
    field: str
    explicit: bool
    value_summary: str


_SCHEMA_HINT_FIELDS = (
    "version",
    "registry",
    "agents",
    "install",
    "sources",
    "skills",
    "groups",
    "use",
)


def _truncate(text: str, *, limit: int = 100) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _summarize_value(value: Any) -> str:
    if isinstance(value, list):
        summary = f"list[len={len(value)}]"
    elif isinstance(value, dict):
        summary = f"dict[len={len(value)}]"
    elif isinstance(value, (int, str, bool)) or value is None:
        summary = repr(value)
    else:
        summary = repr(value)
    return _truncate(summary)


def _raw_top_level_mapping(manifest_path: Path, *, json_output: bool) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise fail(f"invalid YAML in {manifest_path}: {exc}", code=2, json_output=json_output) from exc
    except OSError as exc:
        raise fail(str(exc), code=2, json_output=json_output) from exc

    if not isinstance(raw, dict):
        return {}
    return {key: value for key, value in raw.items() if isinstance(key, str)}


def _schema_hints(manifest_path: Path, *, json_output: bool) -> list[SchemaHint]:
    raw = _raw_top_level_mapping(manifest_path, json_output=json_output)
    defaults = Skillfile().model_dump()
    hints: list[SchemaHint] = []
    for field in _SCHEMA_HINT_FIELDS:
        explicit = field in raw
        value = raw[field] if explicit else defaults[field]
        hints.append(
            {
                "field": field,
                "explicit": explicit,
                "value_summary": _summarize_value(value),
            }
        )
    return hints


def _format_schema_hints(hints: list[SchemaHint]) -> str:
    lines = ["Schema hints:"]
    for hint in hints:
        status = "explicit" if hint["explicit"] else "default"
        line = f"  {status:<8} {hint['field']:<8} = {hint['value_summary']}"
        lines.append(_truncate(line))
    return "\n".join(lines)


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    json_output: bool,
    schema_hints: bool = False,
) -> None:
    if not manifest_path.exists():
        raise fail(f"{manifest_path} not found", code=2, json_output=json_output)

    try:
        manifest = load_manifest(manifest_path)
    except Exception as exc:
        raise fail(str(exc), code=2, json_output=json_output) from exc

    try:
        installed = record_io.read(project_record_path(project_root)).installed
    except Exception as exc:
        raise fail(str(exc), code=2, json_output=json_output) from exc

    skills_root = install_root(project_root)
    findings: list[Finding] = []

    skills = flatten(manifest)
    user_skills = discover_user_skills(project_root)
    skill_names = {skill.name for skill in skills}
    for name in user_skills:
        if name not in skill_names:
            skills.append(SkillEntry(name=name))
            skill_names.add(name)

    manifest_skill_names: set[str] = set()

    # Check 1: every recommended skill is accounted for.
    #
    # Not being installed is a *warning*, not an error: skillfile.yml
    # recommends, it does not compel. A freshly cloned project legitimately
    # has none of them yet, and `skillpod install` is the whole fix. A skill
    # the user already has globally is not missing at all.
    for skill in skills:
        manifest_skill_names.add(skill.name)
        if skill.name in user_skills:
            continue  # lives in .skillpod/user_skills, nothing to install
        materialised = (skills_root / skill.name).exists()
        globally = global_skill_dir(skill.name).is_dir()

        if materialised and globally:
            findings.append(
                Finding(
                    severity="info",
                    code="also-installed-globally",
                    message=(
                        f"'{skill.name}' exists both here and in "
                        f"~/.skillpod/skills/ — the project copy is redundant "
                        f"unless `install.prefer_global` is off"
                    ),
                )
            )
        elif not materialised and globally:
            findings.append(
                Finding(
                    severity="info",
                    code="satisfied-by-global",
                    message=(
                        f"'{skill.name}' is provided by your global install; "
                        f"no project copy was needed"
                    ),
                )
            )
        elif not materialised:
            findings.append(
                Finding(
                    severity="warning",
                    code="not-installed",
                    message=(
                        f"skill '{skill.name}' is recommended by the manifest but "
                        f"not installed — run `skillpod install`"
                    ),
                )
            )

    # Check 2: every recorded skill still has its materialised directory.
    # Here the record and the disk genuinely disagree, which *is* an error.
    for name in installed:
        skill_dir = skills_root / name
        if not skill_dir.exists():
            findings.append(
                Finding(
                    severity="error",
                    code="missing-materialised-dir",
                    message=(
                        f"'{name}' is recorded as installed but its directory is gone"
                    ),
                    path=str(skill_dir),
                )
            )

    # Check 3: every *installed* skill's fan-out resolves into .skillpod/skills/.
    #
    # Skills that are not installed are skipped: they were already reported by
    # check 1, and a missing fan-out is the expected consequence, not a second
    # independent fault. Reporting both would make a freshly cloned project
    # fail `doctor` with errors when all it needs is `skillpod install`.
    for skill in skills:
        if not (skills_root / skill.name).exists():
            continue
        for agent_entry in manifest.agents:
            agent = agent_entry.name
            link = agent_skill_dir(project_root, agent, skill.name)
            if not link.exists() and not link.is_symlink():
                findings.append(
                    Finding(
                        severity="error",
                        code="missing-fanout-symlink",
                        message=f"fan-out symlink for '{skill.name}' under .{agent}/skills/ is missing",
                        path=str(link),
                    )
                )
            elif link.is_symlink() and not is_managed_fanout(link, project_root):
                findings.append(
                    Finding(
                        severity="error",
                        code="unmanaged-fanout-symlink",
                        message=(
                            f"fan-out symlink for '{skill.name}' under .{agent}/skills/ "
                            f"does not point into .skillpod/skills/"
                        ),
                        path=str(link),
                    )
                )

    # Check 4: orphan directories under .skillpod/skills/ not in manifest.
    try:
        if skills_root.exists():
            for child in skills_root.iterdir():
                if child.name not in manifest_skill_names:
                    findings.append(
                        Finding(
                            severity="warning",
                            code="orphan-dir",
                            message=f"'{child.name}' under .skillpod/skills/ is not in the manifest",
                            path=str(child),
                        )
                    )
    except OSError as exc:
        raise fail(str(exc), code=2, json_output=json_output) from exc

    has_errors = any(f["severity"] == "error" for f in findings)
    ok = not has_errors

    payload = {"ok": ok, "findings": list(findings)}
    hints: list[SchemaHint] = []
    if schema_hints:
        hints = _schema_hints(manifest_path, json_output=json_output)
        payload["schema_hints"] = hints

    if json_output:
        emit(payload, json_output=True)
        if not ok:
            raise SystemExit(1)
        return

    if not findings:
        human = "No findings. Project looks healthy."
    else:
        lines: list[str] = []
        for f in findings:
            path_suffix = f" ({f['path']})" if f.get("path") else ""
            lines.append(f"[{f['severity'].upper()}] {f['code']}: {f['message']}{path_suffix}")
        human = "\n".join(lines)

    if schema_hints:
        human += "\n\n" + _format_schema_hints(hints)

    emit(payload, json_output=False, human=human)

    if not ok:
        raise SystemExit(1)


__all__ = ["run"]
