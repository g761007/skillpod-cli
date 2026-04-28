# Changelog

All notable changes to **skillpod** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/g761007/skillpod-cli/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/g761007/skillpod-cli/releases/tag/v0.5.0
