# Changelog

All notable changes to **skillpod** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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

[Unreleased]: https://github.com/g761007/skillpod-cli/compare/v0.5.4...HEAD
[0.5.4]: https://github.com/g761007/skillpod-cli/releases/tag/v0.5.4
[0.5.3]: https://github.com/g761007/skillpod-cli/releases/tag/v0.5.3
[0.5.2]: https://github.com/g761007/skillpod-cli/releases/tag/v0.5.2
[0.5.1]: https://github.com/g761007/skillpod-cli/releases/tag/v0.5.1
[0.5.0]: https://github.com/g761007/skillpod-cli/releases/tag/v0.5.0
