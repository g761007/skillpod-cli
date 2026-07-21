# v0.8.0 / v0.9.0 — The recommendation model

> Goal: reposition `skillfile.yml` from an **enforced dependency manifest** to a
> **project recommendation**. Each developer keeps their own habits; the project
> only suggests. Every open question in the current design resolves once this
> positioning is fixed.
>
> Date: 2026-07-21 · Baseline: v0.7.0 unreleased (444 tests, ruff + mypy strict)

## Why this reframing

The current design is npm-shaped: `skillfile.lock` pins an exact commit per
skill, `resolve.py:36-46` makes that pin **authoritative and sticky** (once
locked, `install` never consults upstream again), and `skillfile.lock` is not
gitignored — it is meant to be committed so the whole team gets byte-identical
skills.

That is precisely the property the project owner does **not** want. Skills are
prompt content, developers have different working styles, and forcing one skill
set on a team is a cost with no matching benefit.

The closest correct analogy is VS Code's `.vscode/extensions.json`
`recommendations`: the project declares intent, the developer decides.

## Locked decisions

- **`skillfile.yml` is advisory.** It declares which skills the project
  *recommends*. Nothing about it is enforced on a developer's machine.
- **Version pinning stays, but moves into the human-authored file.**
  `SkillEntry.version` is already implemented (`sources/resolver.py:26` passes
  `explicit_commit=skill.version`) and is simply undocumented. A recommendation
  may optionally suggest a commit; no machine-generated lockfile is needed.
- **`skillfile.lock` is removed**, replaced by install *records* — local,
  gitignored, descriptive, never prescriptive. Two of them, symmetric:
  `.skillpod/installed.yml` (project) and `~/.skillpod/installed.yml` (global).
- **`install.prefer_global` defaults to `true`.** This **reverses** the earlier
  opt-in decision, which was justified by cross-team reproducibility — a goal
  this positioning drops. "I already have it globally" means the recommendation
  is satisfied. Set `false` to force a project-local copy.
- **Shadowing degrades gracefully.** If an agent's project skill directory fully
  shadows its global one (rather than merging), that agent is treated as having
  **no global layer**: skills install project-locally as normal. Encoded as a
  per-agent capability table, populated empirically — never assumed.
- **Global/project overlap is not an error.** `global-local-conflict` today is
  `severity="error"` with `exit 1` (`global_doctor.py:69-78`). It becomes an
  informational "satisfied by global" note in `skillpod doctor`.

## Model shift

| Concern | Enforced model (today) | Recommendation model (target) |
|---|---|---|
| `skillfile.yml` | Contract | Suggestion |
| Version pin | `skillfile.lock` (generated, committed) | `skills[].version` (authored, optional) |
| Install record | `skillfile.lock` | `installed.yml` × 2 (local, ignored) |
| Skill exists globally | `error: global-local-conflict` | `info: satisfied by global` |
| `install` semantics | Replay pinned commits | Install what the project recommends |
| `link`/`unlink` | Global only, peripheral | Both scopes, the primary personal control |
| Profiles | Project-level filter (inert) | "Which subset am I running right now" |

## Survey: global skills have almost no recoverable provenance

Measured on the author's machine, 2026-07-21 — **87 global skills**:

| Shape | Count | Source recoverable? |
|---|---:|---|
| symlink → `~/.cache/skillpod/…` | 18 | yes — owner/repo + commit + subpath |
| symlink → local dir (`~/.agents/skills/…`) | 33 | local source, no upstream to pull |
| real directory | 36 | **no** — name only |

Only **21%** are upgradable today. Root cause: `install_global`
(`global_install.py:150-210`) always materialises `~/.skillpod/skills/<name>` as
a real-directory copy, while `recover_source` (`profile/snapshot.py:52-75`) can
only reconstruct a source from a **symlink** into the cache. The symlink cases
above are legacy installs from ≤0.5.x plus `global archive` moves.

**This is a pre-existing defect, not one introduced here:** `profile save`
documents itself as recovering sources, but for anything installed by the
current version it emits a name-only profile that is not portable to another
machine. Phase 1 fixes the cause; Phase 2 depends on it.

## Phases

Each phase lands independently and keeps `ruff` + `mypy --strict` + the suite green.
**Every phase ships as its own pull request** — no direct commits to `main` for
implementation work.

### Phase 0 — Pin current behaviour

Write failing tests asserting today's defects, so the fixes are provably real:

- `switch <profile> --scope project` then `sync` leaves `.claude/skills/`
  unchanged (profile is inert — `sync.py` and `pipeline.py` contain zero
  references to `profile`).
- A skill present in `~/.skillpod/skills/` is still cloned into
  `.skillpod/skills/` when the project declares it.
- `install_global` followed by `recover_source` yields no source.

→ **verify:** all three red, for the stated reason.

### Phase 1 — Install records replace the lockfile

- `.skillpod/installed.yml` (project) and `~/.skillpod/installed.yml` (global):
  `{name: {kind, source, ref, commit, subpath, sha256}}`.
- `install_global` and `global_apply.execute_apply` write the global record —
  this is what makes Phase 2 possible at all.
- Drop the sticky-pin branch in `resolve.py`; resolution follows
  `skills[].version` when present, else the source's `ref`.
- `list` / `outdated` / `doctor` read the records.
- Delete `FrozenDriftError` and the "local sources are not lockable" special
  case threaded through `pipeline.py` / `doctor.py` / `sync.py`.
- **Backfill** the global record once from the existing installation using
  `recover_source`; expect ~18/87 resolved, rest marked `kind: unknown`.
- Migration: if `skillfile.lock` exists, seed `.skillpod/installed.yml` from it,
  then print a hint to `git rm skillfile.lock`. **Never delete it automatically** —
  it is a committed file the user owns.

→ **verify:** `install` twice is idempotent; after upstream advances, `install`
picks up the new commit (today it would not); a `version:`-pinned skill stays
put; global install round-trips through `recover_source` with a real source;
migration test starting from an existing `skillfile.lock`.

### Phase 2 — `skillpod global update`

```
skillpod global update                  # every skill with a known git source
skillpod global update <name>...        # named subset
skillpod global update --dry-run        # preview
```

- Reads `~/.skillpod/installed.yml`; for each entry with `kind: git`, re-resolve
  the recorded `ref` and re-materialise when the commit moved.
- **Unknown or local sources are skipped with a console notice, never an error.**
  Exit code stays 0 — a 36-skill unknown population must not fail the command.
- Output groups results: `updated` / `already latest` / `skipped (no source)` /
  `skipped (local)`.
- Re-runs the existing agent fan-out for updated skills so `~/.<agent>/skills/`
  reflects new content.

→ **verify:** upgrade with a moved upstream updates content and record; unchanged
upstream is a no-op; unknown-source skill produces a notice and exit 0; named
subset touches only those skills; `--dry-run` writes nothing.

**Naming decided: `global update`, with `upgrade` as a hidden alias.**

This CLI's established pattern is *same verb, scope prefix*: `list` /
`global list`, `doctor` / `global doctor`, and the whole `global link` /
`unlink` / `archive` family uses plain verbs. `skillpod update` already means
"refresh skills" at project scope, so the global counterpart is
`skillpod global update` — a different verb for the same action at a different
scope would break the one naming rule users have already learned everywhere
else in the tool.

The apt/brew distinction (`update` = refresh metadata, `upgrade` = install newer
versions) does not transfer: skillpod has no separate metadata-refresh step, so
there is no second meaning for `update` to be confused with. Keeping `upgrade`
as a hidden alias costs one line and absorbs the muscle memory.

### Phase 3 — Global-aware deduplication (need #2)

- `install` / `add` check `~/.skillpod/skills/<name>` first; when present, the
  agent merges layers, and `prefer_global` is on → mark *satisfied by global*:
  no download, no project fan-out, no project record entry.
- `install.prefer_global: bool = True` added to `InstallPolicy`.
- Per-agent shadowing table gates this; shadowing agents fall back to a normal
  project install (see Locked decisions).
- `list` gains a source-layer column: `[global]` / `[project]` / `[user]`.
- Move `global-local-conflict` out of `global doctor` — where it silently never
  fires outside a project, since `lockfile_io.read()` returns an empty Lockfile
  for a missing file (`io.py:46-48`) — into `doctor` as an info note.

→ **verify:** with `X` installed globally, declaring `X` produces no
`.skillpod/skills/X`; `prefer_global: false` restores the copy; a shadowing
agent installs project-locally regardless; `list` labels each row correctly.

### Phase 4 — The review surface (need #2, "confirm what's available")

Rebuild `skillpod status` as the single dashboard, replacing today's five-command
jigsaw (`status` + `list` + `global list` + `doctor` + `global doctor`):

```
project:      skillpod-cli
recommends:   7 skills
  satisfied:  5   (3 global · 2 project)
  missing:    1   → skillpod install
  broken:     1   → skillpod doctor
active:       dev (project)
```

→ **verify:** one test per state (satisfied-global / satisfied-project / missing
/ broken); JSON payload shape covered.

### Phase 4b — README, first pass (blocks v0.8.0)

0.8.0 removes the lockfile and flips `prefer_global`. Shipping it behind a README
that still teaches `skillfile.lock` is worse than not shipping. This is a release
blocker, not a follow-up. Target structure: see **README target** below.

→ **verify:** every command in the README is run as written against a scratch
project before publishing; zero surviving references to `skillfile.lock`.

**— ship v0.8.0 here —**

### Phase 5 — Unified link/unlink (need #3)

- `skillpod link <skill>` / `skillpod unlink <skill>` — project scope by default,
  `-g` for global. `global link` / `global unlink` stay as aliases.
- `unlink` severs fan-out only, keeping the cached copy so re-linking needs no
  download (mirrors `unlink_global_fanout`).
- `link` can pull a globally-present skill into a project without re-downloading.

→ **verify:** link/unlink round-trip in both scopes leaves no residue;
cross-layer move performs zero network calls.

### Phase 6 — Make project profiles real (need #1)

- New `installer/project_apply.py` mirroring `global_apply.plan_apply`: compute
  desired fan-out (profile-filtered) vs current managed fan-out, emit `to_link` /
  `to_unlink`.
- `switch --scope project` runs the reconcile instead of only writing a pointer.
- `install` / `sync` respect the active profile and report what was excluded.
- **Profiles filter fan-out only** — `.skillpod/skills/` keeps the full declared
  set, so switching is instant and offline.
- Escape hatch: `--all` ignores the active profile for one run.

→ **verify:** Phase 0's first test flips green; switching profiles changes
`.claude/skills/` contents and switching back restores them; no network on switch.

### Phase 7 — Convergence

- Deprecate `profile use` (alias for `switch`); `switch` with no argument lists
  available profiles instead of erroring.
- README, final pass: fold in `link` / `unlink` and working project profiles;
  re-run every snippet. See **README target** below.
- CHANGELOG + migration note.

**— ship v0.9.0 here —**

## README target

Author's stated priority: **practical features, and making it obvious how to use
them simply.** The current README is 776 lines organised around concepts (how it
works, a full field reference) and never shows the global-profile workflow at
all. Restructure it around tasks:

1. **What it is** — the problem, in two sentences. *Projects recommend skills;
   you decide what to run.*
2. **Install** — one block.
3. **60-second start** — the shortest path that ends in a skill actually working.
4. **"I want to…"** — the task index, and the heart of the document. One runnable
   recipe each, no theory:
   - recommend a set of skills for this project
   - switch my whole global setup with one command
   - update my global skills
   - turn a skill off for a while without deleting it
   - see what I actually have right now
5. **Command reference** — a one-line-per-command table.
6. **`skillfile.yml` reference** — moved down, for people who need it.
7. **How it works** — moved to the end, for people who want it.

Rules: every snippet is run before publishing, not written from memory; no
command appears before the reader has been given a reason to want it; concepts
(the four-layer paths, adapters, cache immutability) surface only where a task
forces them.

## Breaking changes

1. `skillfile.lock` no longer read or written. Migration is automatic on first
   `install`; the stale file is left for the user to remove.
2. `install` follows `ref` instead of replaying a pin — a project tracking `main`
   now receives upstream updates. Intended, but a behaviour change; must be
   prominent in the release notes.
3. `prefer_global: true` default means projects stop materialising skills the
   user already has globally.
4. After Phase 6, an active project profile actually removes fan-out entries.
   Users with a stale active profile will see skills disappear from
   `.claude/skills/` on their next `install`. Mitigation: `install` / `sync`
   print the exclusion list and name the responsible profile.

## Out of scope

- Registry / skills.sh trust policy — untouched.
- Adapter protocol and the `~/.cache/skillpod/` immutable git cache — untouched.
- Global profile switching (`switch --scope global`) already works.
- Retroactively recovering provenance for the 36 unrecoverable global skills.
  They stay `unknown` until reinstalled from a source; `global update` reports
  them so the user can decide.

## Open questions

- **Per-agent shadowing table** must be measured before Phase 3 ships. Blocking
  for that phase only; Phases 1-2 are independent of it.
