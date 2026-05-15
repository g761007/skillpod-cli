# Handoff: skillpod-cli — implement v0.6.3 (Session Shell)

## Current state

- **Branch**: `v0.6.2` (PR #6 open: https://github.com/g761007/skillpod-cli/pull/6)
- **main**: clean (v0.6.1 merged as PR #5)
- **Test count**: 374 passed, 1 skipped
- **v0.6.2 CI**: expect Ubuntu/macOS green; Windows 3.12 pre-existing failure unrelated

## What was completed (v0.6.2)

`src/skillpod/state/` package — `read_active_profile(project_root)` with 3-layer priority
(session env > project file > global file), `write_active_profile`, `clear_active_profile`.

`compose_effective_skillset` reads state active profile when `profile_name=None`.
Priority chain: CLI `--profile` > state active > `activation.default_profile` > None.

New CLI commands: `switch <profile> [--scope project|global|session]`,
`profile use` (alias), `profile current`.

`status` always shows `active profile: NAME (scope: SCOPE)` / `(none)`;
JSON key `"active_profile": {"name": ..., "scope": ...}`.

## Next task: v0.6.3 — Session Shell

### Goal

True sub-shell so `skillpod shell <profile>` spawns `$SHELL` with the profile
env pre-loaded, PS1 prefixed, and a nested-shell guard. No state files needed
since the env is process-local. Multiple terminals can each run different profiles.

### New file: `src/skillpod/cli/commands/shell.py`

```python
# skillpod shell <profile>
def run(
    profile_name: str,
    *,
    project_root: Path,
    manifest_path: Path,
    json_output: bool,
    home: Path | None = None,
) -> None:
```

Logic:

1. **Nest guard**: read `SKILLPOD_SHELL_DEPTH` env; if > 0 → `ProfileError("already inside a skillpod shell; exit first")`.
2. **Validate profile** (optional but recommended): call `load(manifest_path)` and
   `compose_effective_skillset(manifest, project_root, profile_name=profile_name, home=home)`
   to catch unknown-profile errors before spawning.
3. **Build child env**: copy `os.environ`, set:
   - `SKILLPOD_ACTIVE_PROFILE=<profile_name>`
   - `SKILLPOD_SHELL_DEPTH=1` (increment if already set — though guard above prevents nesting)
   - `PS1` modification: prepend `[skillpod:<profile_name>] ` to existing `$PS1`;
     if `$PS1` not set, set it to `[skillpod:<profile_name>] $ `.
     Note: zsh uses `PROMPT` not `PS1` — set both for widest compat.
4. **Spawn shell**: `import subprocess; shell = os.environ.get("SHELL", "/bin/sh"); subprocess.run([shell], env=child_env)` — blocking call.
5. **On exit**: emit nothing (env is process-local, no cleanup needed).

Error path: `ManifestError` / `ProfileError` → exit 1 via `run_with_exit_codes`.

### `sync --scope session` (lightweight, no new fan-out path)

Spec says v0.6.3 does NOT introduce per-session agent dirs. Instead:
`sync --scope session` = `sync` + `compose_effective_skillset(profile_name=session_active_profile)`.

In `src/skillpod/cli/commands/sync.py`, read the active profile from state when
the user passes `--scope session`. The simplest implementation: just read
`read_active_profile(project_root)` at the top of `sync.run` and pass it as
`profile_name` to any resolve/install calls that need it.

Actually, looking at the v0.6.x roadmap note: this is "nice to have". Defer if it
adds complexity — the core deliverable is `skillpod shell`.

### `status` change

Add shell session info when `SKILLPOD_SHELL_DEPTH` is set:

```
Shell session: active (depth=1)
```

In JSON: `"shell_session": {"active": true, "depth": 1}` or `{"active": false}`.

### CLI wiring in `app.py`

```python
from skillpod.cli.commands import shell as shell_cmd

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
```

### New test file: `tests/test_shell.py`

Note: testing shell spawning requires subprocess. Do NOT use pexpect (not in dependencies).
Use `subprocess.run` with a short-circuit flag approach, or just test the logic that
validates inputs without actually spawning.

Recommended approach: test `shell.run` with a monkeypatched `subprocess.run` that
captures the args and env.

```python
# tests/test_shell.py
- test_shell_builds_correct_env  (check SKILLPOD_ACTIVE_PROFILE + SKILLPOD_SHELL_DEPTH)
- test_shell_rejects_nested_invocation  (SKILLPOD_SHELL_DEPTH=1 → ProfileError)
- test_shell_unknown_profile_raises  (profile not in manifest → ProfileError)
- test_shell_spawns_correct_executable  (SHELL=/bin/bash → subprocess args[0] == "/bin/bash")
- test_shell_sets_ps1_prefix  (PS1 in child env starts with "[skillpod:dev] ")
```

`tests/test_cli.py` additions:

```python
- test_shell_command_nested_guard (set SKILLPOD_SHELL_DEPTH=1, expect exit 1)
```

For the actual subprocess spawn test: monkeypatch `subprocess.run` to a no-op that
records its arguments, then assert the captured env contains the right values.

### Key files to read first

```
src/skillpod/cli/commands/switch.py       # pattern for new command module
src/skillpod/cli/commands/status.py       # where to add shell session line
src/skillpod/cli/app.py                   # where to register shell command
src/skillpod/skillset/compose.py          # validate profile before spawn
tests/test_cli.py (tail)                  # append new CLI tests here
```

### Backward-compat constraint

If `SKILLPOD_SHELL_DEPTH` is not set, `skillpod shell` works normally.
All other commands are unaffected — they only read `SKILLPOD_ACTIVE_PROFILE`,
not `SKILLPOD_SHELL_DEPTH`.

### Workflow for next session

1. Merge PR #6 (v0.6.2) if CI is green.
2. Cut branch `v0.6.3` from updated main.
3. Implement `src/skillpod/cli/commands/shell.py`.
4. Wire in `app.py`.
5. Update `status.py` to show shell session depth.
6. Write `tests/test_shell.py` + `tests/test_cli.py` additions.
7. Quality gate: `uv run mypy src/skillpod && uv run ruff check src tests && uv run pytest -q`.
8. Commit: `feat(profile): v0.6.3 — Session Shell (skillpod shell <profile>)`.
9. Open PR targeting main.

### Source of truth

Full v0.6.3 spec in `plans/2026-05-14-v0-6-x-workspace-profiles.md` §v0.6.3 (lines 446–499).
