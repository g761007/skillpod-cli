# v0.7.0 — Profile model beta

> Goal: stabilise the profile model and **extend `+` composition from the
> filter-mode read path to the source-bearing global-apply path**, so
> `skillpod switch dev+reviewer --scope global` downloads + fans out the union.
>
> Date: 2026-06-26 · Baseline: v0.6.5 (436 tests, ruff + mypy strict, PyPI live)

## Locked decisions

- **Composition extends to global apply.** `switch <a>+<b> --scope global` unions
  the operands' `GlobalProfileSkill` lists (preserving `source`/`ref`/`subpath`),
  downloads what's missing, fans out, and snapshots for `--back`.
- **Same-name / different-source → left-wins + warning.** The leftmost operand
  that declares a skill keeps its source; a genuinely different source in a later
  operand is dropped with a `UserWarning`. (Consistent with the existing
  left-to-right dedup in `_compose_multi`.)
- **Operands are local profile names only.** `dev+reviewer` is valid;
  `dev+https://…yml` is rejected (avoids interleaving URL download with union).
- **`--back` records the expression.** The active global profile is stored as the
  literal expression string `dev+reviewer`; undo restores the prior snapshot.
- **Composition is declared stable.** The experimental stderr warning (and its
  `SKILLPOD_DISABLE_EXPERIMENTAL_WARNING` suppressor) is removed.

## Work items

### A. Composition → global apply  (main lift)

- **A1** New `src/skillpod/profile/compose.py`:
  `compose_global_bodies(expr, *, home) -> (expr, GlobalProfileBody)`.
  - Reuses `parse_profile_expr` from `skillset.compose`.
  - Resolves each operand via `resolve_profile_target` (local only —
    `is_remote_target` operand → `ProfileError`).
  - Unions skills by name; on `(source, ref, subpath)` mismatch → keep first,
    `warnings.warn(...)`. Unions `agents` (display only) and first non-null `type`.
  - Returns the merged body named after the expression.
- **A2** Conflict rule implemented in A1 (left-wins + warn).
- **A3** `cli/commands/switch.py` global branch: when `"+" in name`, build the
  body via `compose_global_bodies` instead of `resolve_profile_target`, then feed
  the existing `_apply_global(expr, body, expr, agents=…)` path unchanged.
- **A4** Relax the guard: composition is allowed for `global` (and `session`),
  rejected only for `project` (a project pointer can't materialise a composite).
  `--dry-run` / `--back` / `--agent` keep working (they operate on the merged
  body / snapshot, no special-casing needed).
- **A5** `skillset/compose.py`: remove `_emit_experimental_warning()` + its call +
  the env-var suppressor. `parse_profile_expr` stays (now imported by A1 too).

### B. Docs / freeze  (small)

- **B1** README: promote the resolver precedence chain from the `compose.py`
  docstring into a documented, frozen list
  (`CLI --profile > state active (session > project > global) > default_profile > none`).
- **B2** README: document the two-model layering
  (`GlobalProfileFile` → `as_profile_entry()` → `ProfileEntry`).
- **B3** README: composition semantics — union, left-wins, and the now-supported
  scopes (session + global); drop the "experimental — may change in v0.7.x" line.

### C. Schema  (contained)

- **C1** `skillpod schema --profile` emits the `GlobalProfileFile` JSON Schema;
  default still emits the `Skillfile` schema. Commit the generated
  `schemas/global-profile.schema.json` (+ in-tree `src/skillpod/schemas/` copy).

## Files touched

`profile/compose.py` (new), `skillset/compose.py`, `cli/commands/switch.py`,
`cli/commands/schema.py`, `cli/app.py`, `README.md`, `CHANGELOG.md`,
`schemas/global-profile.schema.json` (+ in-tree copy), and tests
(`tests/test_profile_compose.py` new, plus additions to switch / schema tests).

## Verification

- Unit: union + left-wins conflict (warns), remote-operand rejection, empty expr.
- E2E: `switch dev+reviewer --scope global` against real git fixtures →
  both skills downloaded + fanned out; `--back` restores prior set; `--dry-run`
  shows the merged diff without applying.
- Schema: `skillpod schema --profile --json` validates a sample profile file.
- Gate: `ruff check src tests`, `mypy src/skillpod`, `pytest -q` all green.

## Out of scope (deferred)

- `+URL` composition operands.
- `skillpod audit` command (launch-readiness T2.3).
- Composing into a *project* pointer.
