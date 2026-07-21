"""Typer entry point — wires subcommands from `skillpod.cli.commands`."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from skillpod import __version__
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
    global_link,
    global_list,
    global_unlink,
    global_update,
    install_cmd,
    list_cmd,
    profile_add,
    profile_create,
    profile_current,
    profile_diff,
    profile_export,
    profile_import,
    profile_list,
    profile_remove,
    profile_save,
    profile_show,
    profile_use,
)
from skillpod.cli.commands import (
    init as init_cmd,
)
from skillpod.cli.commands import (
    link as link_cmd,
)
from skillpod.cli.commands import (
    outdated as outdated_cmd,
)
from skillpod.cli.commands import (
    remove as remove_cmd,
)
from skillpod.cli.commands import (
    resolve as resolve_cmd,
)
from skillpod.cli.commands import (
    schema as schema_cmd,
)
from skillpod.cli.commands import (
    search as search_cmd,
)
from skillpod.cli.commands import (
    shell as shell_cmd,
)
from skillpod.cli.commands import (
    status as status_cmd,
)
from skillpod.cli.commands import (
    switch as switch_cmd,
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
    add_completion=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"skillpod {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    ...

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

profile_app = typer.Typer(
    help="Manage workspace profiles.",
    no_args_is_help=True,
)
app.add_typer(profile_app, name="profile", help="Manage workspace profiles.")

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


@app.command(help="Re-create fan-out entries from the install record without re-resolving.")
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


@app.command("schema", help="Print or write a skillpod JSON Schema (skillfile.yml or --profile).")
def schema_command(
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write the schema to this path. Use '-' to write to stdout (JSON form).",
        ),
    ] = None,
    profile: Annotated[
        bool,
        typer.Option(
            "--profile",
            help="Emit the global profile file schema instead of the skillfile.yml schema.",
        ),
    ] = False,
    json: JsonOpt = False,
) -> None:
    project_root = Path.cwd()
    schema_cmd.run(
        project_root=project_root,
        output=output,
        json_output=json or output is not None,
        write=output is not None and str(output) != "-",
        profile=profile,
    )


@global_app.command("list", help="List skills in ~/.skillpod/skills/. Use -a/--agents for per-agent view.")
def global_list_cmd(
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
    agents_view: Annotated[
        bool,
        typer.Option(
            "--agents",
            "-a",
            help="Show per-agent fan-out view (~/.<agent>/skills/) instead of ~/.skillpod/skills/.",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show detailed card view with description and per-agent link indicators.",
        ),
    ] = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    global_list.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
        agents_view=agents_view,
        verbose=verbose,
    )


@global_app.command(
    "archive",
    help="Move global skills into ~/.skillpod/skills/<name> and clean up agent copies.",
)
def global_archive_cmd(
    ctx: typer.Context,
    skill: Annotated[
        list[str] | None,
        typer.Argument(
            help=(
                "Skill name(s) to archive. "
                "Pass '*' to archive every global skill at once. "
                "Omit to show this help."
            )
        ),
    ] = None,
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
    if not skill:
        typer.echo(ctx.get_help())
        raise typer.Exit()
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    skill_names: list[str] = [] if skill == ["*"] else list(skill)
    global_archive.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        skill_names=skill_names,
        json_output=json,
        force=force,
    )


@global_app.command("link", help="Fan-out a globally installed skill to agent directories.")
def global_link_cmd(
    skill: Annotated[str, typer.Argument(help="Skill name to link (must exist in ~/.skillpod/skills/).")],
    agent: Annotated[
        list[str] | None,
        typer.Option(
            "--agent",
            "-a",
            help="Target agent(s). Repeatable. Defaults to all known agents.",
        ),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Overwrite existing entries in agent directories without prompting.",
        ),
    ] = False,
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    global_link.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        skill_name=skill,
        agents=agent,
        yes=yes,
        json_output=json,
    )


@global_app.command("unlink", help="Remove agent fan-out symlinks for a globally installed skill.")
def global_unlink_cmd(
    skill: Annotated[str, typer.Argument(help="Skill name to unlink from agent directories.")],
    agent: Annotated[
        list[str] | None,
        typer.Option(
            "--agent",
            "-a",
            help="Target agent(s). Repeatable. Defaults to all known agents.",
        ),
    ] = None,
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    global_unlink.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        skill_name=skill,
        agents=agent,
        json_output=json,
    )


GlobalUpdateSkills = Annotated[
    list[str] | None,
    typer.Argument(help="Skill name(s) to update. Omit to update every updatable skill."),
]
GlobalUpdateDryRun = Annotated[
    bool,
    typer.Option("--dry-run", help="Show what would change without downloading anything."),
]


def _global_update(skill: list[str] | None, dry_run: bool, json: bool) -> None:
    global_update.run(skills=skill or None, dry_run=dry_run, json_output=json)


@global_app.command(
    "update",
    help=(
        "Refresh globally installed skills to newer upstream content. Skills "
        "with no recoverable source, and those from local directories, are "
        "reported and skipped rather than failing the run."
    ),
)
def global_update_cmd(
    skill: GlobalUpdateSkills = None,
    dry_run: GlobalUpdateDryRun = False,
    json: JsonOpt = False,
) -> None:
    _global_update(skill, dry_run, json)


@global_app.command("upgrade", hidden=True, help="Alias for `global update`.")
def global_upgrade_cmd(
    skill: GlobalUpdateSkills = None,
    dry_run: GlobalUpdateDryRun = False,
    json: JsonOpt = False,
) -> None:
    _global_update(skill, dry_run, json)


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


LinkAgents = Annotated[
    list[str] | None,
    typer.Option("--agent", "-a", help="Target agent(s). Repeatable. Defaults to all."),
]
GlobalScope = Annotated[
    bool,
    typer.Option("--global", "-g", help="Act on the global skill set instead of this project."),
]


@app.command(
    "link",
    help=(
        "Make a skill visible to your agents. Project scope by default, -g for "
        "global. Never downloads: an already-installed skill is copied from "
        "~/.skillpod/skills/ if the project does not have it yet."
    ),
)
def link_command(
    skill: Annotated[str, typer.Argument(help="Skill name to link.")],
    agent: LinkAgents = None,
    is_global: GlobalScope = False,
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Overwrite existing entries (global scope).")
    ] = False,
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    link_cmd.run_link(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        skill_name=skill,
        agents=agent,
        is_global=is_global,
        yes=yes,
        json_output=json,
    )


@app.command(
    "unlink",
    help=(
        "Hide a skill from your agents without deleting it. The materialised "
        "copy stays, so re-linking needs no download."
    ),
)
def unlink_command(
    skill: Annotated[str, typer.Argument(help="Skill name to unlink.")],
    agent: LinkAgents = None,
    is_global: GlobalScope = False,
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    link_cmd.run_unlink(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        skill_name=skill,
        agents=agent,
        is_global=is_global,
        json_output=json,
    )


@app.command("status", help="Show project and profile state.")
def status_command(
    profile: Annotated[
        str | None,
        typer.Option("--profile", "-p", help="Profile to apply (shows effective skills)."),
    ] = None,
    ignore_global: Annotated[
        bool,
        typer.Option("--ignore-global", help="Skip global profiles (~/.skillpod/profiles/)."),
    ] = False,
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    status_cmd.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
        profile_name=profile,
        ignore_global=ignore_global,
    )


@app.command("resolve", help="Show the effective skill set (with optional profile filter).")
def resolve_command(
    profile: Annotated[
        str | None,
        typer.Option("--profile", "-p", help="Profile name to apply as a filter."),
    ] = None,
    explain: Annotated[
        bool,
        typer.Option("--explain", "-e", help="Show the layer origin for each skill."),
    ] = False,
    ignore_global: Annotated[
        bool,
        typer.Option("--ignore-global", help="Skip global profiles (~/.skillpod/profiles/)."),
    ] = False,
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    resolve_cmd.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
        profile_name=profile,
        explain=explain,
        ignore_global=ignore_global,
    )


@profile_app.command("create", help="Create a new empty profile.")
def profile_create_cmd(
    name: Annotated[str, typer.Argument(help="Profile name (letters, digits, hyphens, underscores).")],
    is_global: Annotated[
        bool,
        typer.Option("--global", "-g", help="Create a global profile in ~/.skillpod/profiles/."),
    ] = False,
    profile_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="Profile type label (display only: role / project / task / team)."),
    ] = None,
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    profile_create.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
        name=name,
        is_global=is_global,
        profile_type=profile_type,
    )


@profile_app.command("list", help="List available profiles (project and/or global).")
def profile_list_cmd(
    global_only: Annotated[
        bool,
        typer.Option("--global", "-g", help="Show only global profiles."),
    ] = False,
    project_only: Annotated[
        bool,
        typer.Option("--project", help="Show only project profiles."),
    ] = False,
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    profile_list.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
        global_only=global_only,
        project_only=project_only,
    )


@profile_app.command("show", help="Show the content of a profile.")
def profile_show_cmd(
    name: Annotated[str, typer.Argument(help="Profile name.")],
    is_global: Annotated[
        bool,
        typer.Option("--global", "-g", help="Look in global profiles only."),
    ] = False,
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    profile_show.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
        name=name,
        is_global=is_global,
    )


@profile_app.command("add", help="Add a skill to a profile.")
def profile_add_cmd(
    profile_name: Annotated[str, typer.Argument(help="Profile name.")],
    skill_name: Annotated[str, typer.Argument(help="Skill name to add.")],
    is_global: Annotated[
        bool,
        typer.Option("--global", "-g", help="Target a global profile."),
    ] = False,
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    profile_add.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
        profile_name=profile_name,
        skill_name=skill_name,
        is_global=is_global,
    )


@profile_app.command("remove", help="Remove a skill from a profile.")
def profile_remove_cmd(
    profile_name: Annotated[str, typer.Argument(help="Profile name.")],
    skill_name: Annotated[str, typer.Argument(help="Skill name to remove.")],
    is_global: Annotated[
        bool,
        typer.Option("--global", "-g", help="Target a global profile."),
    ] = False,
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    profile_remove.run(
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
        profile_name=profile_name,
        skill_name=skill_name,
        is_global=is_global,
    )


@app.command("shell", help="Start a sub-shell with a profile pre-activated.")
def shell_command(
    profile: Annotated[str, typer.Argument(help="Profile name to activate.")],
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    shell_cmd.run(
        profile_name=profile,
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
    )


@app.command("switch", help="Set the active profile for a scope (project/global/session).")
def switch_command(
    name: Annotated[
        str,
        typer.Argument(
            help="Profile name, or (global scope) a URL / owner/repo/file.yml to download.",
        ),
    ] = "",
    scope: Annotated[
        str | None,
        typer.Option(
            "--scope",
            "-s",
            help="Scope: project (default inside a project), global, or session (prints export).",
        ),
    ] = None,
    yes_global: Annotated[
        bool,
        typer.Option(
            "--global",
            help="Confirm changing global skills when inside a project root.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Global scope: preview the reconcile without applying."),
    ] = False,
    back: Annotated[
        bool,
        typer.Option("--back", help="Global scope: restore the previous global skill set."),
    ] = False,
    update: Annotated[
        bool,
        typer.Option("--update", help="Global scope: re-download a URL profile even if cached."),
    ] = False,
    agent: Annotated[
        list[str] | None,
        typer.Option(
            "--agent",
            "-a",
            help="Global scope: install to these agents only (repeatable; default all).",
        ),
    ] = None,
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    project_root = _project_root(manifest_path)
    effective_scope = scope or ("project" if manifest_path.is_file() else "global")
    switch_cmd.run(
        name,
        effective_scope,
        project_root=project_root,
        manifest_path=manifest_path,
        json_output=json,
        yes_global=yes_global,
        dry_run=dry_run,
        back=back,
        update=update,
        agents=agent or None,
    )


@profile_app.command(
    "use",
    help="Deprecated alias for `skillpod switch`.",
    deprecated=True,
)
def profile_use_cmd(
    name: Annotated[str, typer.Argument(help="Profile name to activate.")],
    scope: Annotated[
        str | None,
        typer.Option(
            "--scope",
            "-s",
            help="Scope: project (default inside a project), global, or session.",
        ),
    ] = None,
    yes_global: Annotated[
        bool,
        typer.Option(
            "--global",
            help="Confirm writing the global active-profile when inside a project root.",
        ),
    ] = False,
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    project_root = _project_root(manifest_path)
    effective_scope = scope or ("project" if manifest_path.is_file() else "global")
    profile_use.run(
        name,
        effective_scope,
        project_root=project_root,
        manifest_path=manifest_path,
        json_output=json,
        yes_global=yes_global,
    )


@profile_app.command(
    "save",
    help="Snapshot the current global skills into a global profile (recovers sources).",
)
def profile_save_cmd(
    name: Annotated[str, typer.Argument(help="Name for the saved global profile.")],
    description: Annotated[
        str | None,
        typer.Option("--description", "-d", help="Optional human-readable description."),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Overwrite an existing profile of the same name."),
    ] = False,
    json: JsonOpt = False,
) -> None:
    profile_save.run(
        name,
        description=description,
        overwrite=yes,
        json_output=json,
    )


@profile_app.command("current", help="Show the active profile and its scope.")
def profile_current_cmd(
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    profile_current.run(
        project_root=_project_root(manifest_path),
        json_output=json,
    )


@profile_app.command("diff", help="Show skill differences between two profiles.")
def profile_diff_cmd(
    profile_a: Annotated[str, typer.Argument(help="First profile name.")],
    profile_b: Annotated[str, typer.Argument(help="Second profile name.")],
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    profile_diff.run(
        profile_a,
        profile_b,
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
    )


@profile_app.command("export", help="Export a profile to a self-contained YAML file.")
def profile_export_cmd(
    name: Annotated[str, typer.Argument(help="Profile name.")],
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
    out: Annotated[
        Path | None, typer.Option("--out", help="Output file path.")
    ] = None,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    profile_export.run(
        name,
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
        out=out,
    )


@profile_app.command("import", help="Import a profile from a YAML file.")
def profile_import_cmd(
    file: Annotated[Path, typer.Argument(help="Path to exported profile YAML.")],
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
    is_global: Annotated[
        bool, typer.Option("--global", help="Import into global scope.")
    ] = False,
    rename: Annotated[
        str | None, typer.Option("--rename", help="Import under a different name.")
    ] = None,
) -> None:
    manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
    profile_import.run(
        file,
        project_root=_project_root(manifest_path),
        manifest_path=manifest_path,
        json_output=json,
        is_global=is_global,
        rename=rename,
    )


if __name__ == "__main__":  # pragma: no cover
    app()
