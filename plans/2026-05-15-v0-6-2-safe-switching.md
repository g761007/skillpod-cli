# Handoff: skillpod-cli — implement v0.6.2 (Safe Switching)

## Current state

- **Branch**: `v0.6.1` (PR #5 open: https://github.com/g761007/skillpod-cli/pull/5)
- **main**: clean (v0.6.0 merged as PR #4)
- **v0.6.1 CI**: expected same as v0.6.0 (Ubuntu/macOS green; Windows 3.12 pre-existing)
- **Test count**: 348 passed, 1 skipped

## What was completed (v0.6.1)

`ActivationPolicy` model + `activation:` block in skillfile.yml. Four modes
(`strict / merge / fallback / manual`) × `inherit_global` flag.
`_apply_activation_policy()` in compose.py drives the resolution logic.
`EffectiveSkillset.warnings` surfaces non-fatal messages to CLI stderr.
`--ignore-global` flag on `resolve` and `status`.

## Next task: v0.6.2 — Safe Switching

### Goal

Explicit, scoped profile activation — user can set an active profile without
passing `--profile` on every command.  Session scope is env-var only (no
sub-shell); sub-shell is v0.6.3.

### New: `src/skillpod/state/` package

```
src/skillpod/state/
  __init__.py
  active.py      # read_active_profile(project_root) -> (name, scope) | (None, None)
  io.py          # write_active_profile / clear_active_profile per scope
```

Three storage layers (priority order, highest first):

| Scope | Storage | Lifetime |
|---|---|---|
| `session` | `SKILLPOD_ACTIVE_PROFILE` env var | shell session |
| `project` | `<project>/.skillpod/active-profile` (plain text, name on one line) | per-repo |
| `global` | `~/.skillpod/active-profile` (plain text) | user-wide |

`read_active_profile(project_root, home=None)` → `tuple[str | None, str | None]`
Returns `(profile_name, scope_label)` where scope_label ∈ `{"session", "project", "global", None}`.

`home: Path | None = None` injection already established — follow the same pattern.

### compose_effective_skillset change

If caller passes `profile_name=None`, the compose function should check
`read_active_profile(project_root)` before falling through to `activation.default_profile`.
Effective priority chain:

```
CLI --profile > state.active (session > project > global) > activation.default_profile > None
```

New optional kwarg: `active_profile_override: str | None = None` is NOT needed —
just read it internally in compose if `profile_name is None`.

### New CLI commands

| Module | Command | Behaviour |
|---|---|---|
| `cli/commands/switch.py` | `switch <profile> [--scope session\|project\|global]` | Write active-profile to the chosen scope. `--scope session` prints `export SKILLPOD_ACTIVE_PROFILE=<name>` to stdout + hint on stderr. Default scope: `project` when inside a project, `global` otherwise. |
| `cli/commands/profile_use.py` | `profile use <profile> [--scope ...]` | Alias for `switch`, mounted on `profile_app`. |
| `cli/commands/profile_current.py` | `profile current` | Print active profile name and its source scope (or "(none)"). |

Safety gate: `switch --scope global` when inside a project root must require
the user to also pass `--global` flag (or an extra `--yes-modify-global` confirm),
to prevent accidental global writes. Emit a clear error if they omit it.

### status change

After the profiles block, add:

```
active profile: reviewer (scope: session)
```

(Or `(none)` when no active profile.)  In JSON: add `"active_profile": {"name": ..., "scope": ...}`.

### Tests

New file: `tests/test_state_active.py`
- write/read round-trip per scope
- priority order: session env > project file > global file
- clear clears only the target scope
- `switch --scope global` inside a project without `--global` flag → ManifestError / exit 1

`tests/test_cli.py` additions:
- `profile current` with no active profile → "(none)"
- `switch dev --scope project` then `profile current` → "dev (project)"
- `switch dev --scope session` → stdout contains `export SKILLPOD_ACTIVE_PROFILE=dev`
- `resolve` without `--profile` picks up active profile automatically

`tests/test_skillset.py` additions:
- `compose_effective_skillset` uses state active profile when `profile_name=None`
- priority: explicit `profile_name` overrides state

### Backward-compat constraint

If no state files exist and no `SKILLPOD_ACTIVE_PROFILE` env var is set,
`read_active_profile()` returns `(None, None)` → compose behaviour unchanged.
Projects without `state/` package installed are unaffected.

### Key files to read first

```
src/skillpod/skillset/compose.py           # where to read active profile
src/skillpod/cli/commands/status.py        # where to add active profile line
src/skillpod/cli/app.py                    # where to register switch/profile_use/profile_current
src/skillpod/installer/paths.py            # home injection pattern
src/skillpod/profile/io.py                 # home injection reference implementation
tests/test_skillset.py                     # existing activation pattern to extend
```

### Workflow for next session

1. Merge PR #5 (or cut v0.6.2 from v0.6.1 if still open).
2. Cut branch `v0.6.2`.
3. Implement: `state/` package → extend `compose_effective_skillset` → CLI commands → tests.
4. Quality gate: `uv run mypy src/skillpod && uv run ruff check src tests && uv run pytest -q`.
5. Commit: `feat(profile): v0.6.2 — Safe Switching (scoped active profile)`.
6. Open PR targeting main.

### Source of truth

Full v0.6.2 spec in `plans/2026-05-14-v0-6-x-workspace-profiles.md` §v0.6.2.
