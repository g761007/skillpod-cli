"""Typer entry point — wires subcommands from `skillpod.cli.commands`."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from skillpod.cli.commands import (
    adapter as adapter_cmd,
)
from skillpod.cli.commands import (
    add as add_cmd,
)
from skillpod.cli.commands import (
    doctor as doctor_cmd,
)
from skillpod.cli.commands import (
    global_archive,
    global_doctor,
    global_list,
    install_cmd,
    list_cmd,
)
from skillpod.cli.commands import (
    init as init_cmd,
)
from skillpod.cli.commands import (
    outdated as outdated_cmd,
)
from skillpod.cli.commands import (
    remove as remove_cmd,
)
from skillpod.cli.commands import (
    schema as schema_cmd,
)
from skillpod.cli.commands import (
    search as search_cmd,
)
from skillpod.cli.commands import (
    sync as sync_cmd,
)
from skillpod.cli.commands import (
    update as update_cmd,
)

app = typer.Typer(
    name="skillpod",
    help="Project-scoped, reproducible skill dependency manager.",
    no_args_is_help=True,
    add_completion=False,
)

global_app = typer.Typer(
    help="Inspect and archive global agent skill directories.",
    no_args_is_help=True,
)
app.add_typer(global_app, name="global", help="Inspect global agent skill directories.")

adapter_app = typer.Typer(
    help="Inspect and manage the adapter registry.",
    no_args_is_help=True,
)
app.add_typer(adapter_app, name="adapter", help="Inspect the active adapter registry.")

ManifestOpt = Annotated[
    Path,
    typer.Option(
        "--manifest",
        "-m",
        help="Path to skillfile.yml (default: ./skillfile.yml).",
        show_default=True,
    ),
]
JsonOpt = Annotated[
    bool,
    typer.Option("--json", help="Emit machine-readable JSON instead of text."),
]


def _project_root(manifest: Path) -> Path:
    """The project root is the directory containing the manifest."""
    p = manifest.expanduser().resolve()
    return p.parent if p.parent.exists() else Path.cwd()


@app.command(help="Bootstrap a new skillfile.yml in the current directory.")
def init(
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    project_root = Path.cwd()
    manifest_path = (project_root / manifest).resolve() if not manifest.is_absolute() else manifest
    init_cmd.run(
        project_root=project_root,
        manifest_path=manifest_path,
        json_output=json,
    )


@app.command(help="Install every skill declared in skillfile.yml.")
def install(
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    install_cmd.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
    )


@app.command(
    help=(
        "Add skill(s) to skillfile.yml and install them. The positional argument "
        "is either a bare skill name (legacy: resolved against declared sources / "
        "registry) or a source identifier (git URL, owner/repo shorthand, or local "
        "path). With a source, the matching `sources:` entry is auto-added."
    ),
)
def add(
    target: Annotated[
        str,
        typer.Argument(
            help="Skill name OR source (git URL / owner/repo / local path).",
        ),
    ],
    skill: Annotated[
        list[str] | None,
        typer.Option(
            "--skill",
            "-s",
            help="Specific skill(s) to install from the source. Use '*' for all. Repeatable.",
        ),
    ] = None,
    agent: Annotated[
        list[str] | None,
        typer.Option(
            "--agent",
            "-a",
            help=(
                "Target agent(s). Repeatable. Project-mode: must be declared in the "
                "manifest. Not valid with --global."
            ),
        ),
    ] = None,
    list_only: Annotated[
        bool,
        typer.Option(
            "--list",
            "-l",
            help="List skills available in the source without installing.",
        ),
    ] = False,
    global_install: Annotated[
        bool,
        typer.Option(
            "--global",
            "-g",
            help="Install to ~/.skillpod/skills/ instead of the project.",
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Skip interactive prompts and replace existing global entries.",
        ),
    ] = False,
    ref: Annotated[
        str | None,
        typer.Option(
            "--ref",
            help="Git ref / branch / commit (default: the remote's default branch).",
        ),
    ] = None,
    source_name: Annotated[
        str | None,
        typer.Option(
            "--source-name",
            help="Override the auto-derived source name written to skillfile.yml.",
        ),
    ] = None,
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    add_cmd.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        target=target,
        skills=skill,
        agents=agent,
        list_only=list_only,
        global_install=global_install,
        yes=yes,
        ref=ref,
        source_name=source_name,
        json_output=json,
    )


@app.command(help="Remove a skill from skillfile.yml and uninstall it.")
def remove(
    skill: Annotated[str, typer.Argument(help="Skill name to remove.")],
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    remove_cmd.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        skill_name=skill,
        json_output=json,
    )


@app.command("list", help="List installed skills and their resolved sources.")
def list_(
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    list_cmd.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
    )


@app.command(help="Re-create fan-out entries from skillfile.lock without re-resolving.")
def sync(
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
    agent: Annotated[
        str | None,
        typer.Option(
            "--agent",
            help="Re-render only this agent's fan-out directory (omit for all agents).",
        ),
    ] = None,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    sync_cmd.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
        agent=agent,
    )


@adapter_app.command("list", help="List the active adapter for each declared agent.")
def adapter_list(
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    adapter_cmd.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
    )


@app.command("search", help="Search the registry for skills matching a query.")
def search(
    query: Annotated[str, typer.Argument(help="Skill name or query term.")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Maximum rows to display.")] = 20,
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    search_cmd.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        query=query,
        limit=limit,
        json_output=json,
    )


@app.command("outdated", help="Show which locked skills have drifted from upstream.")
def outdated(
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    outdated_cmd.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
    )


@app.command("update", help="Re-resolve and refresh skills in the lockfile.")
def update(
    skill: Annotated[str | None, typer.Argument(help="Skill name to update (omit for all).")] = None,
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    update_cmd.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        skill_name=skill,
        json_output=json,
    )


@app.command("doctor", help="Verify manifest/lockfile/symlink consistency.")
def doctor(
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
    schema_hints: Annotated[
        bool,
        typer.Option(
            "--schema-hints",
            "-s",
            help="Also report which top-level skillfile.yml fields are explicit vs using defaults.",
        ),
    ] = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    doctor_cmd.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
        schema_hints=schema_hints,
    )


@app.command("schema", help="Print or write the JSON Schema for skillfile.yml.")
def schema_command(
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write the schema to this path. Use '-' to write to stdout (JSON form).",
        ),
    ] = None,
    json: JsonOpt = False,
) -> None:
    project_root = Path.cwd()
    schema_cmd.run(
        project_root=project_root,
        output=output,
        json_output=json or output is not None,
        write=output is not None and str(output) != "-",
    )


@global_app.command("list", help="List global skills across known agents.")
def global_list_cmd(
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    global_list.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
    )


@global_app.command(
    "archive",
    help="Move matching global skills into ~/.skillpod/skills/<name> and clean up agent copies.",
)
def global_archive_cmd(
    skill: Annotated[str, typer.Argument(help="Global skill name to archive.")],
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Overwrite ~/.skillpod/skills/<name> when it exists with different content.",
        ),
    ] = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    global_archive.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        skill_name=skill,
        json_output=json,
        force=force,
    )


@global_app.command("doctor", help="Check global skills for advisory conflicts.")
def global_doctor_cmd(
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    global_doctor.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
    )


if __name__ == "__main__":  # pragma: no cover
    app()
