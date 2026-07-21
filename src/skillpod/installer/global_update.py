"""Refresh globally installed skills to newer upstream content.

The counterpart to `skillpod update` at project scope. Both re-resolve against
the ref that was followed and re-materialise whatever moved; neither is a side
effect of installing.

**Nothing here fails the command.** A global skill set is heterogeneous and
largely uncurated — on the author's machine 37 of 88 skills have no recoverable
origin and 33 more come from local directories with no upstream at all. Aborting
because one entry cannot be refreshed would make the command useless on exactly
the population it exists to serve. Every skill that cannot be updated is
reported in its own group and the run continues.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path

from skillpod.installer.global_apply import fetch_source
from skillpod.installer.global_backfill import reconcile_global_record
from skillpod.installer.global_install import agents_with_skill, install_global
from skillpod.record.models import SkillRecord
from skillpod.sources.discovery import discover_skills
from skillpod.sources.errors import SourceError
from skillpod.sources.git import resolve_default_branch, resolve_ref
from skillpod.sources.spec import parse_source_spec


@dataclass
class SkillUpdate:
    """One skill whose upstream has moved since it was installed."""

    name: str
    source: str  # expanded to a real git URL, not the recorded shorthand
    ref: str
    from_commit: str
    to_commit: str
    subpath: str | None = None


@dataclass
class UpdatePlan:
    to_update: list[SkillUpdate] = field(default_factory=list)
    current: list[str] = field(default_factory=list)
    skipped_local: list[str] = field(default_factory=list)
    skipped_unknown: list[str] = field(default_factory=list)
    unreachable: list[tuple[str, str]] = field(default_factory=list)

    @property
    def has_work(self) -> bool:
        return bool(self.to_update)


@dataclass
class UpdateReport:
    updated: list[SkillUpdate] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


def _one_line(exc: Exception) -> str:
    """Collapse a multi-line git failure to something a table can hold."""
    first = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
    return first if len(first) <= 120 else first[:117] + "..."


def _selected(
    installed: dict[str, SkillRecord], names: Iterable[str] | None
) -> dict[str, SkillRecord]:
    if names is None:
        return installed
    wanted = set(names)
    return {name: rec for name, rec in installed.items() if name in wanted}


def plan_update(
    *,
    names: Iterable[str] | None = None,
    home: Path | None = None,
    persist_record: bool = True,
) -> tuple[UpdatePlan, list[str]]:
    """Work out what would change, without changing any skill.

    The record is reconciled first, so skills installed before provenance was
    tracked are classified rather than silently absent. ``persist_record=False``
    keeps that reconciliation in memory — `--dry-run` promises to touch nothing,
    and writing a file the user did not ask for would break that promise even
    though the contents are only a restatement of what is already on disk.

    Returns the plan plus the names the caller asked for that are not installed.
    """
    record, _report = reconcile_global_record(home, persist=persist_record)
    unknown_names = (
        sorted(set(names) - set(record.installed)) if names is not None else []
    )

    plan = UpdatePlan()
    for name, rec in sorted(_selected(record.installed, names).items()):
        if rec.kind == "unknown":
            plan.skipped_unknown.append(name)
            continue
        if rec.kind == "local":
            plan.skipped_local.append(name)
            continue
        if not rec.source or not rec.commit:
            plan.skipped_unknown.append(name)
            continue

        # A recovered source is often the `owner/repo` shorthand, which git
        # itself does not understand — expanding it is what parse_source_spec
        # is for, and skipping that step made every GitHub-sourced skill look
        # unreachable.
        spec = parse_source_spec(rec.source, ref=rec.ref)
        if spec is None or spec.kind != "git":
            plan.skipped_unknown.append(name)
            continue
        url = spec.url_or_path

        try:
            # A record with no ref came from a lockfile or a cache symlink,
            # neither of which stored one. The remote's default branch is the
            # only honest guess, and a successful update records it properly.
            ref = spec.ref or resolve_default_branch(url)
            latest = resolve_ref(url, ref)
        except Exception as exc:  # network, auth, deleted repo, bad URL
            plan.unreachable.append((name, _one_line(exc)))
            continue

        if latest == rec.commit:
            plan.current.append(name)
        else:
            plan.to_update.append(
                SkillUpdate(
                    name=name,
                    source=url,
                    ref=ref,
                    from_commit=rec.commit,
                    to_commit=latest,
                    subpath=rec.subpath or spec.subpath,
                )
            )

    return plan, unknown_names


def execute_update(plan: UpdatePlan, *, home: Path | None = None) -> UpdateReport:
    """Re-materialise every skill in ``plan.to_update``.

    Each skill is refreshed independently: one failure does not stop the rest,
    it lands in ``report.failed``.
    """
    report = UpdateReport()
    for item in plan.to_update:
        try:
            _refresh(item, home=home)
        except Exception as exc:
            report.failed.append((item.name, _one_line(exc)))
        else:
            report.updated.append(item)
    return report


def _refresh(item: SkillUpdate, *, home: Path | None) -> None:
    spec = parse_source_spec(item.source, ref=item.ref)
    if spec is None:
        raise SourceError(
            f"source {item.source!r} is not a recognised git URL, "
            "owner/repo, or local path"
        )
    if item.subpath:
        spec = replace(spec, subpath=item.subpath)
    spec, root, _commit = fetch_source(spec)
    discovered = discover_skills(root, root_name=spec.derived_name)
    match = next((d for d in discovered if d.name == item.name), None)
    if match is None:
        available = ", ".join(d.name for d in discovered) or "<none>"
        raise SourceError(
            f"skill {item.name!r} is no longer present in {item.source} "
            f"(available: {available})"
        )

    # Put it back only where it already was, and force past the content
    # difference that is the entire reason we are here.
    install_global(
        spec,
        [match],
        agents=agents_with_skill(item.name, home) or None,
        force=True,
        home=home,
    )


__all__ = [
    "SkillUpdate",
    "UpdatePlan",
    "UpdateReport",
    "execute_update",
    "plan_update",
]
