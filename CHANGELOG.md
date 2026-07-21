# Changelog

All notable changes to **skillpod** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed

- **`skillfile.lock` is gone.** It existed to force byte-identical skills
  across a team, which is the opposite of what `skillfile.yml` now means: a
  **recommendation**, not a contract. Each developer decides what to run.
  See `plans/2026-07-21-recommendation-model.md`.

  On the first `install` after upgrading, an existing `skillfile.lock` is read
  once to seed the new record so nothing is re-downloaded. The file itself is
  **never deleted** — it is committed and yours to remove (`git rm
  skillfile.lock`).

### Added

- **`skillpod global update [skill...]`** — refresh globally installed skills
  to newer upstream content, with `--dry-run` to preview and an optional list
  of names to narrow the run. `global upgrade` is a hidden alias.

  It is built to stay useful on a skill set nobody curated. Skills whose origin
  cannot be recovered, ones installed from local directories, and remotes that
  cannot be reached are each **reported in their own group and skipped** — none
  of them fails the command, and one dead remote does not stop the rest. On the
  author's 88 global skills that is 18 updatable, 33 local, 37 unknown.

  The record is reconciled before planning, so a skill set that predates
  install records is classified rather than reported as empty. `--dry-run`
  keeps that reconciliation in memory and writes nothing at all.
- **Install records** — `.skillpod/installed.yml` (project) and
  `~/.skillpod/installed.yml` (global) record what is materialised on *this*
  machine. Both live under `.skillpod/`, which `skillpod init` already
  gitignores, so a record never lands in a commit. Unlike the lockfile they
  describe rather than prescribe, which is why they can express two things it
  could not: **local sources** (nothing to pin, but definitely installed) and
  **`kind: unknown`** (provenance that could not be recovered).
- **Profile composition now works for global apply** —
  `skillpod switch dev+reviewer --scope global` unions the operands'
  source-bearing skills, downloads what is missing, and fans out the combined
  set. Operands must be **local profile names** (a `+URL` operand is rejected).
  Same-named skills resolve **left-wins**: the leftmost operand that declares a
  skill keeps its source; a later operand with a genuinely different source is
  dropped with a warning. `--dry-run`, `--back`, and `--agent` all work with a
  composed switch.
- **`skillpod schema --profile`** — emit the JSON Schema for a global profile
  file (`~/.skillpod/profiles/<name>.yml`); the default still emits the
  `skillfile.yml` schema. Generated `schemas/global-profile.schema.json` is
  committed for editor integration.

### Changed

- **`install` no longer chases upstream, and no longer replays a pin.**
  Resolution follows the manifest — the source's `ref`, or an authored
  `skills[].version`. A skill that is already installed and still matches what
  the manifest declares is skipped without touching the network, so a repeat
  `install` is offline and instant. Asking for newer content is now
  exclusively `skillpod update`, which re-resolves and re-materialises.
- **`skillpod doctor`: "recommended but not installed" is a warning, not an
  error.** A freshly cloned project has none of its recommended skills yet;
  that is not a broken state, and `doctor` says to run `skillpod install`
  instead of exiting 1. Record and disk *disagreeing* is still an error.
- **`skillpod global doctor`: overlap with a project is informational.**
  `global-local-conflict` (error, exit 1) becomes `global-local-overlap`
  (info, exit 0) — keeping a skill both globally and in a project is a
  legitimate choice, not a fault.
- `skillpod outdated` compares recorded commits against upstream and skips
  entries with nothing to compare (local sources, unknown provenance) rather
  than reporting them as drifted.
- **Profile composition is no longer experimental.** The one-time stderr
  warning and the `SKILLPOD_DISABLE_EXPERIMENTAL_WARNING` suppressor are
  removed; composition semantics (union, left-wins dedup, session + global
  scopes) are stable. The frozen profile resolution order and the two-layer
  profile model are now documented in the README.

### Internal

- New `skillpod.record` package (models, I/O, legacy-lockfile migration);
  `skillpod.lockfile` deleted. `hash_directory` moved to `skillpod.integrity`
  — it is used by fan-out and global install and never belonged to the
  lockfile. `FrozenDriftError` and the "local sources are not lockable"
  special case are both gone.
- `ResolvedSkill` gains `ref`, so a record can distinguish "tracking main"
  from "pinned to this SHA".
- New `skillpod.profile.compose.compose_global_bodies` — a source-bearing union
  of multiple global profiles with left-wins conflict handling.
- 11 new tests (global compose union + left-wins conflict + remote-operand
  rejection, end-to-end composite `switch --scope global`, `--back` round-trip,
  `schema --profile`); the 3 obsolete composition experimental-warning tests
  removed. `ruff` and `mypy --strict` clean across 85 files.

## [0.6.5] — 2026-06-26

### Added

- **Global profiles that download & swap skills (`skillpod switch <name> --scope global`)** —
  a standalone profile at `~/.skillpod/profiles/<name>.yml` whose skills carry an
  inline `source` (git URL / `owner/repo` / local path, with optional `ref` / `subpath`).
  Switching to it reconciles the global per-agent fan-out (`~/.<agent>/skills/`):
  - skills missing from `~/.skillpod/skills/` are **downloaded** from their source;
  - the profile's skills are **fanned out** to the declared agents;
  - managed skills the profile no longer lists are **unlinked**, keeping the
    `~/.skillpod/skills/` cache copy for instant re-activation;
  - the profile is recorded as the active global profile.
  - **Target agents are chosen at switch time**, not in the profile — pass
    `--agent`/`-a` (repeatable) to scope the fan-out, or omit it to install to
    all supported agents. A profile is just a skill set.
  - `--dry-run` previews the download / link / unlink diff without applying.
  - A skill missing with no source to download from is **skipped with a warning**
    (so legacy name-only profiles still apply what they can).
  - An unmanaged real directory at a fan-out target is never overwritten — it
    raises a conflict instead of deleting the user's content.
- **`switch --scope global --back`** — restore the previous global skill set
  (single-level undo; the prior set is snapshotted before every global switch).
- **Switch from a URL** — `switch <url-or-owner/repo/path.yml> --scope global`
  downloads the profile to `~/.skillpod/profiles/` when not already present
  (`--update` forces a refresh). Supports direct `https://…/<file>.yml` and the
  `owner/repo/path/<file>.yml` raw.githubusercontent shorthand.
- **`skillpod profile save <name>`** — snapshot the current global skill set into a
  profile, recovering each skill's `source` best-effort from its cache symlink so
  the profile is portable.
- Global profile files gain optional `name` and `description` fields (like a skill).
- Skill entries in a global profile accept both the bare-name form and the object
  form `{name, source, ref?, subpath?}`.
- **`skillpod --version`** — eager flag on the main callback that prints
  `skillpod <version>` and exits 0, while preserving `no_args_is_help`.
- **Shell completion enabled** (`add_completion=True`) — `skillpod` now ships
  `--install-completion` and `--show-completion`.

### Changed

- **`__version__` is now single-sourced from package metadata**
  (`importlib.metadata.version("skillpod")`, with a `0.0.0+dev` fallback for an
  uninstalled source tree). Previously it was hardcoded and had drifted to
  `0.5.6` while the package shipped `0.6.4`.
- **`skillpod add` human output now shows the resolved `url@commit`** so you can
  see exactly which source and commit were pulled into your agents.

### Docs

- README gains a **Quickstart** path, a **Security model / what you're
  trusting** section (registry trust ≠ git/local trust; `SKILL.md` is read into
  agent context; pin commits via the lockfile), a `--json` scriptability
  highlight, and a pre-1.0 schema-stability notice.
- `SECURITY.md` supported-version table updated from `0.5.x` to `0.6.x`.

### Internal

- New `skillpod.installer.global_apply` (reconcile engine: `plan_apply` /
  `execute_apply` / `managed_global_skills`) and `unlink_global_fanout`
  (fan-out-only removal that preserves the cache).
- New `skillpod.profile.snapshot` (source recovery + profile writer),
  `skillpod.profile.fetch` (URL resolution), and `skillpod.state.history`
  (single-level undo). `switch --scope global` orchestrates them.
- New `GlobalProfileSkill` / `GlobalProfileBody` models; `GlobalProfileFile.as_profile_entry()`
  keeps filter-mode `load_global_profile` backward-compatible (name-only `ProfileEntry`).
- 24 new tests (model normalisation, reconcile classification, end-to-end download +
  fan-out from a real git source, agent-narrowing, unmanaged-data protection,
  source recovery, save, `--back` round-trip, URL fetch via respx, CLI dry-run vs
  apply); `ruff` and `mypy --strict` clean.

## [0.6.4] — 2026-05-15

### Added

- **Profile composition (`+` operator, experimental)** — `skillpod switch dev+reviewer --scope session`
  activates the union of two profiles in a single command. Skills and agents are merged
  left-to-right with deduplication.
  - `parse_profile_expr("dev+reviewer")` → `["dev", "reviewer"]` (public helper in `skillpod.skillset.compose`).
  - First use emits a one-time stderr warning: `warning: profile composition is experimental — semantics may change in v0.7.x`.
    Suppress with `SKILLPOD_DISABLE_EXPERIMENTAL_WARNING=1`.
  - Composition expressions are **session-scope only** — passing `--scope project` or `--scope global` raises an error.
- **`skillpod profile diff <a> <b>`** — shows added / removed / common skills between two profiles.
  `+` prefix for added, `-` for removed, two-space indent for common. `--json` emits `{"added", "removed", "common"}`.
- **`skillpod profile export <name> [--out FILE]`** — exports a profile to a self-contained YAML file
  with a `skillpod_profile_export` header and `exported_at` / `source_scope` metadata.
  Prints to stdout when `--out` is omitted.
- **`skillpod profile import <file> [--global] [--rename NAME]`** — imports an exported profile.
  Project scope writes to `.skillpod/imported/<name>.yml`; global scope writes to `~/.skillpod/profiles/<name>.yml`.
  Both locations are auto-discovered by the profile resolver. `--rename` overrides the embedded name.

### Internal

- 27 new tests (composition engine, profile diff, export/import round-trips, CLI integration); 407 passed, 1 skipped.
- `mypy --strict` clean across 79 files.

## [0.6.3] — 2026-05-15

### Added

- **`skillpod shell <profile>`** — spawns `$SHELL` (fallback `/bin/sh`) with the named profile
  pre-activated as environment variables. No state files; env is process-local so multiple terminals
  can each run different profiles simultaneously.
  - Sets `SKILLPOD_ACTIVE_PROFILE=<name>` and `SKILLPOD_SHELL_DEPTH=1` in the child env.
  - Prefixes `PS1` and `PROMPT` with `[skillpod:<profile>] ` for visual context.
  - **Nest guard**: running `skillpod shell` inside an existing shell session (`SKILLPOD_SHELL_DEPTH > 0`) exits with an error — exit the inner shell first.
  - Profile is validated before spawning; unknown profiles raise an error (exit 1).
- **`skillpod status`** now shows `shell session: active (depth=N)` when executed inside a `skillpod shell` session. JSON output gains `"shell_session": {"active": true, "depth": N}`.

### Internal

- 6 new tests (env building, nest guard, unknown profile, executable, PS1 prefix, CLI guard); 380 passed, 1 skipped.

## [0.6.2] — 2026-05-15

### Added

- **`skillpod switch <profile> [--scope project|global|session]`** — set the active profile
  without passing `--profile` to every command.
  - `--scope project` (default when inside a project): writes `.skillpod/active-profile`.
  - `--scope global`: writes `~/.skillpod/active-profile`. Requires explicit `--global` confirm flag when run from inside a project root to prevent accidental global mutations.
  - `--scope session`: prints `export SKILLPOD_ACTIVE_PROFILE=<name>` to stdout (eval in your shell: `eval "$(skillpod switch <name> --scope session)"`).
- **`skillpod profile use <profile>`** — alias for `skillpod switch`.
- **`skillpod profile current`** — print the currently active profile and its scope. JSON: `{"active_profile": <name>, "scope": <scope>}` or `null` when none is set.
- **State layer system** (`skillpod.state`): active profile priority is `SKILLPOD_ACTIVE_PROFILE` env var > `.skillpod/active-profile` (project) > `~/.skillpod/active-profile` (global).
- **`compose_effective_skillset`** auto-reads state active profile when `--profile` is not passed. Full priority chain: CLI `--profile` > state active > `activation.default_profile` > none.
- **`skillpod status`** always shows `active profile: NAME (scope: SCOPE)` (or `(none)`). JSON gains `"active_profile": {"name": ..., "scope": ...}` and renames the old `"active_profile"` string field to `"profile_filter"`.

### Internal

- `src/skillpod/state/` package: `read_active_profile`, `write_active_profile`, `clear_active_profile`.
- 14 new state tests + 8 new CLI tests; 374 passed, 1 skipped.

## [0.6.1] — 2026-05-14

### Added

- **`activation.mode`** field in `skillfile.yml` — controls how project and global profiles interact:
  - `manual` (default): profile is applied only when explicitly requested; global profiles eligible as fallback.
  - `strict`: only project-defined profiles accepted; global profiles blocked entirely.
  - `merge`: union of project and global profile skills/agents; project wins on conflict.
  - `fallback`: project profile first; falls back to global profile if not found in project.
- **`activation.inherit_global`** (bool, default `true`): when `false`, global profile look-up is skipped regardless of mode.
- **`activation.default_profile`** (string, optional): profile activated automatically when no `--profile` flag is passed.
- Cross-check validators in `Skillfile`: profiles that reference unknown agents or unknown skills are rejected at load time.

### Internal

- `ActivationPolicy` Pydantic model; extended `_apply_activation_policy` in `compose_effective_skillset`.
- Fixture directories `tests/fixtures/multi_project_a/` and `tests/fixtures/multi_project_b/` for isolation tests.

## [0.6.0] — 2026-05-14

### Added

- **`profiles:` section in `skillfile.yml`** — define named working contexts that filter which skills and agents are active:
  ```yaml
  profiles:
    reviewer:
      type: role
      skills: [code-review, audit]
      agents: [claude, codex]
  ```
- **`skillpod profile create <name> [--type role|project|team|custom]`** — create a new empty profile.
- **`skillpod profile list [--global] [--json]`** — list all profiles (project and/or global).
- **`skillpod profile show <name> [--global]`** — display a profile's type, skills, and agents.
- **`skillpod profile add <profile> <skill>`** — add a skill reference to a profile.
- **`skillpod profile remove <profile> <skill>`** — remove a skill reference from a profile.
- **`skillpod resolve --profile <name>`** — resolve the effective skill set with a profile filter applied.
- **`skillpod resolve --explain`** — show per-skill provenance (project / user_skill / profile_filter / global_profile_filter).
- **`skillpod status --profile <name>`** — show status filtered to a specific profile.
- Global profile storage under `~/.skillpod/profiles/<name>.yml` (auto-created by `profile create --global`).

### Internal

- `src/skillpod/profile/` package: `ProfileEntry` model, `get_project_profile`, `load_global_profile`, `ProfileError`.
- `src/skillpod/skillset/` package: `compose_effective_skillset`, `EffectiveSkillset`, `LayerOrigin`.
- JSON Schema regenerated for v0.6.0 models.

## [0.5.7] — 2026-05-14

### Added

- **`skillpod global link <name> [--agent ...]`** — fan-out an existing
  `~/.skillpod/skills/<name>` to agent dirs (`~/.<agent>/skills/<name>`) as
  symlinks, without re-fetching from source. `--yes/-y` replaces existing
  entries; omitting `--agent` links to every known agent
  (claude / codex / gemini / cursor / opencode / antigravity).
- **`skillpod global unlink <name> [--agent ...]`** — remove managed
  symlinks pointing into `~/.skillpod/skills/<name>`. Unmanaged entries
  (real directories or symlinks pointing elsewhere) are skipped with a
  warning, never overwritten.
- **`skillpod global list -v/--verbose`** — Unicode box card view per skill
  with description parsed from `SKILL.md` YAML frontmatter, ●/○ full-name
  agent indicators, human-readable size, and install path. Terminal width is
  capped at 100 cols for readability.
- Shared helper `paths.is_managed_global_fanout(name, agent_dir)` exposing
  the "is this agent entry a managed symlink into `~/.skillpod/skills/`"
  predicate for reuse across list / link / unlink / archive.

### Changed

- **`skillpod global list` default view now shows the install root**
  (`~/.skillpod/skills/`) as a compact NAME / LINKED / SIZE / MTIME table.
  `LINKED` shows `all`, `-`, or an abbreviated agent list
  (`cl,cx,ge,cu,oc,ag`). `MTIME` is date-only (`YYYY-MM-DD`). The previous
  per-agent fan-out view is preserved as `--agents/-a`.
- `installer.global_install._materialise_agent_link` promoted to public
  `materialise_agent_link` so the new `global link` command can reuse it.
- `global_archive` refactored to use the shared `is_managed_global_fanout`
  helper (−24 lines, no behaviour change).

### Removed

- `openspec/` is no longer tracked in git. The directory remains usable
  locally; its references in `README.md` (specs link) and `CONTRIBUTING.md`
  (OpenSpec workflow section) are removed.

### Internal

- 11 new tests covering global list (install-root / agents views), link,
  and unlink; 278 passed, 1 skipped.
- `mypy --strict` clean across 55 files.

## [0.5.6] — 2026-04-28

### Added

- **`skillpod global archive` now supports batch and wildcard modes.**
  - No arguments: prints usage help.
  - `skillpod global archive '*'`: archives every global skill found across all agent directories
    in one pass (quote the asterisk to prevent shell glob expansion).
  - `skillpod global archive alpha beta …`: archives exactly those named skills.
  - Single-name behaviour is unchanged: immediate error on missing skill, single-skill JSON payload.
  - Skills already managed by skillpod (`~/.skillpod/skills/<name>` exists and every agent copy is
    a symlink pointing there) are automatically skipped in wildcard and multi-name modes and
    reported as `skipped_managed` in the JSON output.

- **`skillpod add` now accepts browser tree URLs pointing at a subdirectory
  inside a repository.** URLs of the form
  `https://github.com/<owner>/<repo>/tree/<ref>/<subpath>` (GitHub) and
  `https://gitlab.com/<org>/<repo>/-/tree/<ref>/<subpath>` (GitLab) are
  parsed automatically: the repo is cloned once, and the specified subpath
  is used as the discovery root so only skills inside that directory are
  visible and installed. The resolved `url`, `ref`, and `subpath` are
  persisted in `skillfile.yml` for reproducible reinstalls. Passing
  `--ref` overrides the ref embedded in the URL.
- `SourceEntry` in `skillfile.yml` now supports an optional `subpath:` field
  (git sources only) to record the subdirectory offset from the repo root.
  Hand-authored manifests targeting a monorepo subdirectory can set this
  field directly.
- `SourceSpec` dataclass gains a `subpath` attribute; `sources.git.resolve_git`
  and the global-install path both honour it when navigating to the skill
  directory within a cloned repo.
- All previously undocumented-but-working input forms are now documented in
  the README: full GitHub/GitLab HTTPS URLs, SSH SCP-style (`git@…:…`),
  `ssh://` URLs, and local paths.

### Changed

- **Breaking:** `skillpod add <source> --global/-g` now installs only to
  `~/.skillpod/skills/<name>/` and no longer creates
  `~/.<agent>/skills/<name>` fan-out entries. Passing `-a/--agent` with
  `--global` now exits with an error; `-a/--agent` remains valid for
  project-mode source installs.

## [0.5.5] — 2026-04-28

### Fixed

- **`skillpod add owner/repo` now auto-detects the remote's default
  branch.** Previously `--ref` defaulted to `"main"`, so adding a
  repository whose default branch is `master` (e.g.
  `alchaincyf/huashu-design`) failed with `git ls-remote --exit-code
  <url> main` returning exit 2. The CLI option now defaults to `None`;
  when omitted, the resolver runs `git ls-remote --symref <url> HEAD` to
  discover the actual default branch and writes the concrete name (e.g.
  `master`) into `skillfile.yml` for reproducibility. Explicit `--ref`
  values continue to be respected.

## [0.5.4] — 2026-04-28

### Fixed

- **`skillpod add owner/repo` now works for single-skill repositories
  whose `SKILL.md` lives at the repo root.** Previously discovery named
  the skill after the cache directory basename (e.g.
  `repo@<commit>` — and therefore unstable across commits), and the git
  resolver failed because it always probed `<repo_root>/<skill_name>/`
  rather than treating the repo root itself as the skill. The CLI now
  passes the URL-derived name (e.g. `repo` from `owner/repo`) into
  discovery, and `resolve_git` falls back to `<repo_root>` when the
  named subdir is absent but `<repo_root>/SKILL.md` exists.

### Changed

- **Install root is now a real-directory copy, not a symlink into the
  cache.** `.skillpod/skills/<name>/` (project) and
  `~/.skillpod/skills/<name>/` (global) are materialised via
  `shutil.copytree` from the source. Previously they were symlinks
  pointing into `~/.cache/skillpod/<host>/<org>/<repo>@<commit>/`, which
  meant clearing the cache (manually or by macOS housekeeping) silently
  broke every installed skill.
- Re-running `install` / `add -g` is hash-idempotent: when the install
  root's content already matches the source, no rewrite happens. When
  content differs, the install fails unless `--yes / -y` is passed
  (matching the previous force semantics).
- Agent fan-out (`.<agent>/skills/<name>`, `~/.<agent>/skills/<name>`)
  continues to default to `symlink`. Targets now resolve to a real
  directory rather than via the cache, so cache pruning is safe.

### Migration

- Existing installs whose `.skillpod/skills/<name>/` is a legacy symlink
  are upgraded to a real-directory copy on the next `install`, `sync`, or
  `add -g` run — no manual intervention required.

## [0.5.3] — 2026-04-28

### Changed

- `skillpod search` now queries the public skills.sh fuzzy-search endpoint
  (`GET /api/search?q=<query>&limit=<n>`) instead of the assumed-but-missing
  per-skill detail route (`/api/skills/<name>`, which 404s on the public
  deployment). Results are now multi-row and reflect installs from the live
  registry. `--limit` caps how many rows are displayed.
- The search API does not expose `verified` or `stars`; those columns now
  render as `-` (and JSON `null`). `passes_policy` is computed from the
  signals that *are* available: `allow_unverified` plus the `min_installs`
  threshold.

### Added

- `skillpod.registry.search()` and `SearchHit` dataclass for the
  search-discovery surface; exported from `skillpod.registry`.

### Notes

- `skillpod.registry.lookup()` is preserved against the historical
  per-skill detail contract for the install pipeline. Switching the install
  path to the public registry requires a separate change (resolve via
  `/api/search` + GitHub API for commit SHAs).

## [0.5.2] — 2026-04-28

### Changed

- `skillpod global archive <name>` now **moves** matching skills into
  `~/.skillpod/skills/<name>/` and removes the agent-directory copies
  (previously appended a `.archived-<timestamp>` suffix in place). When the
  destination already exists with different content, archive aborts unless
  `--force/-f` is passed; symlinks pointing at the destination are unlinked
  in place.

## [0.5.1] — 2026-04-28

### Added

- `skillpod add` now accepts a **source identifier** (git URL, GitHub
  `owner/repo` shorthand, SCP-style SSH, `.git`, or local path) in addition
  to a bare skill name. Source-shaped inputs trigger `SKILL.md` discovery
  inside the source and append the matching `sources:` entry to
  `skillfile.yml` automatically — no hand-editing required. Modeled after
  `npx skills add` from vercel-labs/skills.
- New `add` flags: `-s/--skill` (select skills from the source, repeatable,
  `*` for all), `-a/--agent` (filter fan-out to a subset of declared agents,
  repeatable), `-l/--list` (preview skills in the source without installing),
  `-g/--global` (install to `~/.skillpod/skills/` and fan-out to
  `~/.<agent>/skills/`), `-y/--yes` (skip prompts, replace existing global
  entries), `--ref` (pin git ref/branch/commit, default `main`),
  `--source-name` (override the auto-derived source name written to the
  manifest).
- `skillpod.sources.spec.parse_source_spec` recognises git URLs, SCP-style
  SSH (`git@host:org/repo`), `.git` suffixes, local paths
  (`./`, `../`, `/`, `~`) and GitHub `owner/repo` shorthand.
- `skillpod.sources.discovery.discover_skills` walks a fetched source for
  `SKILL.md` files (depth ≤ 2) and parses YAML frontmatter for
  `description:`, with a graceful fallback for malformed frontmatter.
- `skillpod.installer.global_install` materialises skills under
  `~/.skillpod/skills/<name>` and fans them out to `~/.<agent>/skills/<name>`
  for the agents you select.
- `installer.install(...)` gains an optional `agent_filter` parameter that
  restricts fan-out to a subset of manifest agents in a single run, without
  mutating the manifest.

### Changed

- Bare-name `skillpod add <skill>` now refuses source-only flags
  (`-l`/`-s`/`-g`/`-a`/`--source-name`) with a clear error instead of
  silently ignoring them.

## [0.5.0] — 2026-04-27

First public release on PyPI. Bundles every roadmap milestone shipped through
the 0.1.0 → 0.4.0 internal series, plus the packaging and documentation work
required to publish.

### Added

- **Public packaging**: `pip install skillpod` now resolves from PyPI.
- `LICENSE` (MIT) shipped in source distribution and wheel.
- `src/skillpod/py.typed` marker so downstream projects pick up the type hints
  declared under `mypy --strict`.
- Full project metadata in `pyproject.toml`: license file pointer, OSI/OS/Topic
  classifiers, `project.urls` (Repository, Issues, Changelog), Python 3.13.
- Logo and brand assets under `docs/assets/`.
- Community files: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`,
  GitHub issue templates, and a pull request template.
- CI now runs on Linux, macOS, and Windows (Windows allowed to soft-fail until
  the symlink-mode adapter ships first-class Windows support) and adds a
  `mypy --strict` step.
- `release.yml` workflow that publishes to PyPI via OIDC Trusted Publisher when
  a `v*` tag is pushed.
- `skillpod schema` CLI command that exports the JSON Schema for
  `skillfile.yml` from the pydantic models to stdout via `--json`, or to a file
  via `--output PATH`.
- Generated `schemas/skillfile.schema.json` committed to the repo so editors
  (VS Code, JetBrains) can consume it directly for autocomplete and validation,
  with a link from the README's Field reference.
- `skillpod doctor --schema-hints` / `-s` flag that reports which top-level
  `skillfile.yml` fields are user-explicit versus using model defaults;
  surfaces in both human and `--json` output.
- Project-level `cspell.config.yaml` with the project's terminology and
  `en,en-GB` language so editors stop flagging Commonwealth-English spellings
  and skillpod-specific identifiers.

### Changed

- `Development Status` classifier promoted from `3 - Alpha` to `4 - Beta`.
- README rewritten around real, working CLI usage instead of "planned" copy.
- All four pre-release OpenSpec changes archived under `openspec/changes/archive/`
  and synced into `openspec/specs/`.
- `examples/skillfile.yml` rewritten as a full schema reference with
  `[required]` / `[optional, default: …]` / `[conditional]` markers on every
  key.
- `README.md` gains a "Field reference" section with per-block tables
  (top-level, `registry`, `agents[]`, `install`, `sources[]`, `skills[]`) plus
  a "JSON Schema" subsection.
- `skillpod init` now writes an annotated skeleton with commented-out `install`
  and `registry` defaults, instead of the previous 4-line minimum manifest.
- `openspec/specs/manifest/spec.md` Purpose replaced with a real description;
  new requirements "Install policy fields" and "Agent entry forms"; the
  minimal-manifest scenario now includes `install.fallback`'s default of
  `["copy"]`.

## [0.4.0] — 2026-04-27 (internal)

### Added

- Per-agent **adapter layer** (`installer/adapter*.py`) with pluggable
  `Adapter` protocol and default `IdentityAdapter`.
- `install.mode` now accepts `symlink | copy | hardlink` plus an
  `install.fallback` chain when the primary mode fails (e.g. Windows
  symlink rejection or cross-filesystem hardlinks).
- `skillpod adapter list` command — show active adapters per agent.
- `skillpod sync --agent <id>` — re-fan-out a single agent without touching
  the others.
- Cross-filesystem device probe before hardlink fan-out; downgrades to copy
  with a warning when source/target live on different mounts.

## [0.3.0] — 2026-04-27 (internal)

### Added

- `groups:` section in `skillfile.yml` with selectable bundles (`default`,
  `dev`, custom names) — install resolves the chosen groups.
- `user_skills:` priority resolution — user-scoped skills win over project
  skills with the same name.
- `skillpod global list` / `archive` / `doctor` advisory commands for inspecting
  and managing global skill directories under `~/.<agent>/skills`.

## [0.2.0] — 2026-04-27 (internal)

### Added

- Trust policy: `min_installs` / `min_stars` thresholds enforced during
  registry discovery and `skillpod search`.
- `skillpod search`, `skillpod outdated`, and `skillpod doctor` diagnostic
  commands.
- Manifest field for trust policy (per-skill overrides allowed).

## [0.1.0] — 2026-04-27 (internal)

### Added

- Initial bootstrap of the install pipeline:
  - `skillfile.yml` manifest with pydantic v2 schema.
  - `skillfile.lock` lockfile pinned to a git commit per skill.
  - Source resolver covering `git`, `github`, and `skills.sh` discovery.
  - Registry-discovery layer talking to skills.sh (read-only).
  - Installer that materialises skills into `.skillpod/skills/` and fans out
    symlinks to `.claude/skills`, `.codex/skills`, `.gemini/skills`,
    `.cursor/skills`, `.opencode/skills`, `.antigravity/skills`.
- Typer-based CLI: `init`, `add`, `remove`, `install`, `list`, `sync`,
  `update`.
- pytest suite covering manifest, lockfile, source resolution, installer,
  and CLI smoke tests.

[0.6.5]: https://github.com/g761007/skillpod-cli/compare/v0.6.4...v0.6.5
[0.6.4]: https://github.com/g761007/skillpod-cli/compare/v0.6.3...v0.6.4
[0.6.3]: https://github.com/g761007/skillpod-cli/compare/v0.6.2...v0.6.3
[0.6.2]: https://github.com/g761007/skillpod-cli/compare/v0.6.1...v0.6.2
[0.6.1]: https://github.com/g761007/skillpod-cli/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/g761007/skillpod-cli/compare/v0.5.7...v0.6.0
[0.5.7]: https://github.com/g761007/skillpod-cli/compare/v0.5.6...v0.5.7
[0.5.6]: https://github.com/g761007/skillpod-cli/compare/v0.5.5...v0.5.6
[0.5.5]: https://github.com/g761007/skillpod-cli/releases/tag/v0.5.5
[0.5.4]: https://github.com/g761007/skillpod-cli/releases/tag/v0.5.4
[0.5.3]: https://github.com/g761007/skillpod-cli/releases/tag/v0.5.3
[0.5.2]: https://github.com/g761007/skillpod-cli/releases/tag/v0.5.2
[0.5.1]: https://github.com/g761007/skillpod-cli/releases/tag/v0.5.1
[0.5.0]: https://github.com/g761007/skillpod-cli/releases/tag/v0.5.0
