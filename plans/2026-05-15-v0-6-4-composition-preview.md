# Handoff: skillpod-cli — implement v0.6.4 (Composition Preview)

## Current state

- **Branch**: `main` (clean, v0.6.3 merged as PR #7)
- **Test count**: 380 passed, 1 skipped
- **Quality gate**: mypy 76 files clean, ruff clean

## What was completed (v0.6.3)

`src/skillpod/cli/commands/shell.py` — `skillpod shell <profile>`:
- Nest guard via `SKILLPOD_SHELL_DEPTH`
- Profile validation via `compose_effective_skillset`
- Child env: `SKILLPOD_ACTIVE_PROFILE`, `SKILLPOD_SHELL_DEPTH=1`, `PS1`/`PROMPT` prefix
- Blocking `subprocess.run([shell], env=child_env)`

`status` shows `shell session: active (depth=N)` when inside a shell.

## Next task: v0.6.4 — Composition Preview

### Goal

Experimental `+` operator: `skillpod switch dev+reviewer` activates a
union of two profiles. Add `profile diff`, `profile export`, `profile import`
commands. All composition paths emit an experimental stderr warning.

### Source of truth

Full spec: `plans/2026-05-14-v0-6-x-workspace-profiles.md` §v0.6.4 (lines ~500–575).

---

### Step-by-step

1. `git checkout -b v0.6.4` from main.

2. **Add `parse_profile_expr` to `src/skillpod/skillset/compose.py`**:

   ```python
   def parse_profile_expr(expr: str) -> list[str]:
       """Split a '+'-separated profile expression into a list of names."""
       return [p.strip() for p in expr.split("+") if p.strip()]
   ```

3. **Extend `compose_effective_skillset`** — detect composition:

   When `profile_name` contains `+`, call `_compose_multi`:
   - Parse with `parse_profile_expr`
   - Print experimental warning to stderr (once, regardless of profile count)
   - For each profile name, call `_apply_activation_policy` independently
   - Union `skills` (deduped, order: left-to-right)
   - Union `agents` (deduped, order: left-to-right)
   - Build a synthetic `ProfileEntry` and proceed as single-profile path
   - Any single profile not found → raise `ProfileError` immediately

   Keep existing single-profile path untouched. The `profile_name: str | None`
   signature does NOT change — callers pass `"dev+reviewer"` as-is.

   Experimental warning (print to `sys.stderr`, not `warnings.warn`):
   ```
   warning: profile composition is experimental — semantics may change in v0.7.x
   ```
   Suppress when env var `SKILLPOD_DISABLE_EXPERIMENTAL_WARNING=1` is set.

4. **Create `src/skillpod/cli/commands/profile_diff.py`**:

   ```python
   def run(
       name_a: str,
       name_b: str,
       *,
       project_root: Path,
       manifest_path: Path,
       json_output: bool,
       home: Path | None = None,
   ) -> None:
   ```

   Logic:
   - Load manifest; call `compose_effective_skillset` for each name
   - Compute sets: `skills_a`, `skills_b`
   - `added` = `skills_b - skills_a`, `removed` = `skills_a - skills_b`, `common` = intersection
   - JSON: `{"added": [...], "removed": [...], "common": [...]}`
   - Human:
     ```
     + skill-x
     + skill-y
     - skill-z
       skill-common
     ```

5. **Create `src/skillpod/cli/commands/profile_export.py`**:

   ```python
   def run(
       name: str,
       *,
       project_root: Path,
       manifest_path: Path,
       json_output: bool,
       out: Path | None = None,
       home: Path | None = None,
   ) -> None:
   ```

   Logic:
   - Resolve profile via `get_project_profile` or `load_global_profile`
   - Build export dict with metadata:
     ```yaml
     skillpod_profile_export: "1"
     exported_at: "2026-05-15T09:00:00Z"
     source_scope: project
     profile:
       name: reviewer
       type: role
       skills: [...]
       agents: [...]
     ```
   - If `out` given: write to file; else print to stdout
   - JSON mode: emit the dict as JSON

6. **Create `src/skillpod/cli/commands/profile_import.py`**:

   ```python
   def run(
       file: Path,
       *,
       project_root: Path,
       manifest_path: Path,
       json_output: bool,
       is_global: bool = False,
       rename: str | None = None,
       home: Path | None = None,
   ) -> None:
   ```

   Logic:
   - Read YAML; validate `skillpod_profile_export` key present
   - Extract `profile.name` (override with `rename` if given)
   - Validate profile name regex (`^[a-z][a-z0-9-]*$`) — no `+` allowed
   - If `is_global`: write to `~/.skillpod/profiles/<name>.yml` (new file per profile)
   - Else: append/overwrite in project manifest's `profiles:` section
     (use `ruamel.yaml` to preserve formatting — or write a standalone YAML file
     to `.skillpod/imported/<name>.yml` if ruamel is not available)
   - Check activation policy `strict` if writing to project — raise `ProfileError`
     if policy would block it (consistent with v0.6.1)
   - Emit: `imported profile 'NAME' to SCOPE` on success

   **Simpler fallback if manifest YAML editing is too complex**: write to
   `.skillpod/imported/<name>.yml` and load it in `profile/io.py` as an
   additional project-scope source.

7. **Wire in `src/skillpod/cli/app.py`**:

   ```python
   from skillpod.cli.commands import profile_diff, profile_export, profile_import

   @profile_app.command("diff", help="Show skill differences between two profiles.")
   def profile_diff_cmd(
       profile_a: Annotated[str, typer.Argument(help="First profile name.")],
       profile_b: Annotated[str, typer.Argument(help="Second profile name.")],
       manifest: ManifestOpt = Path("skillfile.yml"),
       json: JsonOpt = False,
   ) -> None:
       manifest_path = manifest if manifest.is_absolute() else (Path.cwd() / manifest).resolve()
       profile_diff.run(
           profile_a, profile_b,
           project_root=_project_root(manifest_path),
           manifest_path=manifest_path,
           json_output=json,
       )

   @profile_app.command("export", help="Export a profile to a self-contained YAML file.")
   def profile_export_cmd(
       name: Annotated[str, typer.Argument(help="Profile name.")],
       manifest: ManifestOpt = Path("skillfile.yml"),
       json: JsonOpt = False,
       out: Annotated[Path | None, typer.Option("--out", help="Output file path.")] = None,
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
       is_global: Annotated[bool, typer.Option("--global", help="Import into global scope.")] = False,
       rename: Annotated[str | None, typer.Option("--rename", help="Import under a different name.")] = None,
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
   ```

8. **Write `tests/test_composition.py`**:

   ```python
   - test_parse_profile_expr_single          # "dev" → ["dev"]
   - test_parse_profile_expr_two             # "dev+reviewer" → ["dev", "reviewer"]
   - test_parse_profile_expr_strips_spaces   # "dev + reviewer" → ["dev", "reviewer"]
   - test_compose_multi_union_skills         # skills from a + skills from b, deduped
   - test_compose_multi_order_stable         # "a+b" vs "b+a" yields consistent union (sorted output)
   - test_compose_multi_unknown_profile_raises  # one bad name → ProfileError
   - test_compose_multi_experimental_warning   # composition → stderr contains "experimental"
   - test_compose_single_no_warning            # single profile → no experimental warning
   - test_experimental_warning_suppressed      # SKILLPOD_DISABLE_EXPERIMENTAL_WARNING=1 → no warn
   ```

9. **Write `tests/test_profile_diff.py`**:

   ```python
   - test_diff_added_removed_common
   - test_diff_symmetric  # diff(a,b) added == diff(b,a) removed
   - test_diff_json_output
   - test_diff_unknown_profile_raises
   ```

10. **Write `tests/test_profile_export_import.py`**:

    ```python
    - test_export_produces_valid_yaml
    - test_export_to_file
    - test_export_json_output
    - test_export_unknown_profile_raises
    - test_import_round_trip  # export then import, profile survives
    - test_import_rename
    - test_import_invalid_file_raises
    - test_import_missing_header_raises  # no skillpod_profile_export key
    ```

11. **Append to `tests/test_cli.py`**:

    ```python
    - test_profile_diff_command
    - test_profile_export_command
    - test_profile_import_command
    - test_switch_composition_experimental_warning  # "dev+reviewer" → warning on stderr
    ```

12. **Quality gate**:

    ```bash
    uv run mypy src/skillpod && uv run ruff check src tests && uv run pytest -q
    ```

13. **Commit**:

    ```
    feat(profile): v0.6.4 — Composition Preview (profile + operator, diff/export/import)
    ```

14. Push + open PR targeting main.

---

### Key files to read first

```
src/skillpod/skillset/compose.py          # where to add parse_profile_expr + multi path
src/skillpod/cli/commands/profile_show.py # pattern for diff/export command modules
src/skillpod/cli/commands/switch.py       # handles profile_name; passes through as-is
src/skillpod/profile/io.py                # get_project_profile, load_global_profile
src/skillpod/cli/app.py                   # wiring location (profile_app subcommands)
tests/test_cli.py (tail)                  # append new CLI tests here
```

### Important patterns

- Command module signature: `def run(arg, *, project_root, manifest_path, json_output, home=None) -> None`
  with inner `_run()` wrapped by `run_with_exit_codes`
- Import in `app.py`: `from skillpod.cli.commands import profile_diff, profile_export, profile_import`
- `ProfileError` → exit 1 (already wired in `run_with_exit_codes`)
- No new Pydantic models needed — composition is pure resolver behaviour

### Constraints

- `profile_name` regex in `manifest/models.py` already bans `+` in stored profiles — this is correct; the `+` is only a *query-time* operator, never stored
- `switch <a+b>` calls `write_active_profile` with the literal `"a+b"` string — that's fine since `SKILLPOD_ACTIVE_PROFILE` is env-only for session scope; project/global file scope should raise `ProfileError("composition expressions cannot be persisted; use --scope session")`
- Do NOT change `profile_name: str | None` signature of `compose_effective_skillset` — it would break all 14+ callers

### Deferred

- `LayerOrigin.PROFILE_FILTER` extended with `source_profiles: tuple[str, ...]` metadata — out of scope for v0.6.4 (frozen dataclass refactor is v0.7.x material)
- `sync --scope session` with per-session agent dir — still deferred per v0.6.3 decision

---

### Notes

- Windows CI failure on Python 3.12 is pre-existing; not introduced by this work
- Memory: release goes directly to main (no PR), but PRs are used for feature branches
- `profile import` complexity: if editing the YAML manifest in-place is too risky,
  use the `.skillpod/imported/<name>.yml` sidecar approach and load it in `profile/io.py`
