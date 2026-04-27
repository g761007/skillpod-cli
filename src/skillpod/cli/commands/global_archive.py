"""`skillpod global archive` — non-destructively rename global skill dirs."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from skillpod.cli._output import emit, fail
from skillpod.cli.commands.global_list import scan_global_skills


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    skill_name: str,
    json_output: bool,
) -> None:
    matches = [Path(row["path"]) for row in scan_global_skills() if row["name"] == skill_name]
    if not matches:
        raise fail(f"global skill {skill_name!r} not found", code=1, json_output=json_output)

    blocked = [path for path in matches if _is_inside(path, project_root)]
    if blocked:
        raise fail(
            "refusing to archive project-local paths: "
            + ", ".join(str(path) for path in blocked),
            code=1,
            json_output=json_output,
        )

    suffix = datetime.now(UTC).strftime("archived-%Y%m%d-%H%M%S")
    archived: list[dict[str, str]] = []
    for path in matches:
        target = path.with_name(f"{path.name}.{suffix}")
        path.rename(target)
        archived.append({"from": str(path), "to": str(target)})

    payload = {"ok": True, "archived": archived}
    if json_output:
        emit(payload, json_output=True)
        return

    lines = ["Archived global skill directory:" if len(archived) == 1 else "Archived global skill directories:"]
    lines.extend(f"  {row['from']} -> {row['to']}" for row in archived)
    emit(payload, json_output=False, human="\n".join(lines))


__all__ = ["run"]
