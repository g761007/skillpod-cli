# Global Profile Apply — Switchable, Self-Sourced Global Skill Sets

**Date:** 2026-06-22
**Status:** implemented — 14 new tests, ruff/mypy clean, full suite 421 passed

## Problem

Today a global profile (`~/.skillpod/profiles/<name>.yml`) is *filter-mode only*:
its `skills:` are plain name strings, and `skillpod switch --scope global` merely
writes a pointer file — it never materialises anything. There is no way to make a
global profile a self-contained, switchable skill set whose activation actually
changes what is fanned out into `~/.<agent>/skills/`.

## Goal

Make a global profile behave like a global `skillfile.yml`:

1. Each skill may carry an **inline source** (git URL / `owner/repo` / local path)
   so it can be resolved without any project context.
2. **Applying** a profile reconciles the global per-agent fan-out so the active
   global skill set equals that profile.
3. Skills missing from `~/.skillpod/skills/` are **auto-downloaded** from their
   source during apply.

## Decisions (user-confirmed)

- **Source representation:** inline `source` string per skill, parsed by the
  existing `parse_source_spec`.
- **Switch semantics:** sync/reconcile, but **preview first** — show the diff and
  require `--yes` to execute.
- **Download:** auto-download missing skills (with a source) during apply.

## Design

### Schema (backward compatible)

`skills:` items may be a bare string (name only) **or** an object:
`{name, source?, ref?, subpath?}`. Existing name-only files keep working.

### Models — `src/skillpod/profile/models.py`

- `GlobalProfileSkill{name, source, ref, subpath}` (`extra="forbid"`).
- `GlobalProfileBody{type, agents, skills: list[GlobalProfileSkill]}` with a
  `mode="before"` validator normalising bare strings → `{"name": s}`.
- `GlobalProfileFile{version, profile: GlobalProfileBody}` gains
  `as_profile_entry() -> ProfileEntry` (names only) for filter-mode callers.
- `ProfileEntry` (manifest/models.py) is **unchanged** — filter mode untouched.

### I/O — `src/skillpod/profile/io.py`

- `_load_profile_file` returns `as_profile_entry()` so `load_global_profile`
  keeps its `ProfileEntry` return (back-compat).
- New `load_global_profile_body(name, home) -> GlobalProfileBody | None` exposes
  the source-bearing body for apply.

### Reconcile engine — `src/skillpod/installer/global_apply.py` (new)

- `plan_apply(body, home) -> ApplyPlan{to_download, to_link, to_unlink, unresolved, agents}`.
  - desired = profile skill names; present = `~/.skillpod/skills/` entries.
  - missing + has source → `to_download`; missing + no source → `unresolved`.
  - present but not fully fanned-out to target agents → `to_link`.
  - managed fan-out skills not in desired → `to_unlink`.
- `execute_apply(plan, body, home, force)`:
  - download via `parse_source_spec` → `_fetch_source` → `discover_skills` →
    `install_global(spec, [skill], agents=body.agents, force)`.
  - link present skills via `materialise_agent_link`.
  - unlink via new `unlink_global_fanout(name, agents, home)` — **fan-out only,
    keeps the install-root cache**.

### Command — `src/skillpod/cli/commands/profile_apply.py` (new)

`skillpod profile apply <name> [--yes] [--json]`:
- load body; error if profile missing or any `unresolved`.
- print the plan; without `--yes` stop (preview). With `--yes` execute, then
  `write_active_profile(name, "global")` and emit a report.

### Wiring — `src/skillpod/cli/app.py`

Add `@profile_app.command("apply")`.

## Tests

- `tests/test_profile_io.py`: model normalisation (bare + object), `as_profile_entry`,
  `load_global_profile_body`.
- `tests/test_global_apply.py` (new): `plan_apply` classification; end-to-end apply
  with a real `file://` git fixture (download + fan-out); switching profiles unlinks
  the previous set; preview changes nothing.
- `tests/test_cli.py`: `profile apply` preview vs `--yes`.

## Out of scope

- Changing `switch`/`shell` (they stay lightweight pointer writers).
- Registry-by-name resolution (inline source only for now).
- Project-profile apply (this is global-only).
