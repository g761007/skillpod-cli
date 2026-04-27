# Add skillpod MVP install pipeline (Roadmap 0.1.0)

## Why

`plans/skillpod-plan.md` §1 identifies four pain points the project must solve:

1. **Skill bloat** — global skill directories accumulate untracked tools that
   pollute every agent.
2. **Multi-agent maintenance** — the same skill must currently be copied into
   `.claude/skills`, `.codex/skills`, `.gemini/skills`, etc.
3. **Non-reproducible installs** — there is no lockfile, so a skill can change
   under the user's feet between machines or commits.
4. **Discovery gap** — no shared registry exists; users hand-curate URLs.

skillpod takes the npm/cargo model — a declarative `skillfile.yml`, a
git-commit-pinned `skillfile.lock`, and a project-local install root that
fans out to each agent via symlinks. This change establishes the MVP needed
to make that pipeline work end-to-end. Subsequent changes (0.2.0+) layer
trust policy, groups, and per-agent adapters on top.

## What Changes

This change introduces six capabilities that together form the install
pipeline:

- **manifest** — parse `skillfile.yml` (version, registry, agents, install,
  sources, skills) into a typed model with deterministic defaults.
- **lockfile** — write/read `skillfile.lock`, recording git source URL,
  commit SHA, and content sha256. Registry name is *not* stored
  (plans/skillpod-plan.md §4.4).
- **source-resolver** — resolve `local` and `git` sources, honouring source
  `priority`, with the global cache at
  `~/.cache/skillpod/<host>/<org>/<repo>@<ref>/`.
- **registry-discovery** — query skills.sh for unspecified skills to obtain
  a GitHub repo + ref, then hand off to source-resolver. Network failure
  fails the operation; no silent fallback.
- **installer** — orchestrate the pipeline `read manifest -> resolve ->
  fetch -> write .skillpod/skills/<name> -> symlink fan-out -> write
  lockfile`. Default mode is symlink; conflicts abort.
- **cli** — Typer-based CLI exposing `init`, `install`, `add`, `remove`,
  `list`, `sync`. All subcommands accept `--manifest <path>` and `--json`.

The implementation lands a Python 3.11+ package (`src/skillpod/...`) with
sub-packages mirroring the six capabilities, and end-to-end tests that
install fixtures into a throwaway project.

## Impact

- New artefacts in user repos:
  - `skillfile.yml`, `skillfile.lock`, `.skillpod/skills/<name>/`,
    `.skillpod/user_skills/`, plus symlinks under each declared agent
    directory.
- New shared cache: `~/.cache/skillpod/`. Safe to delete; reproducibility
  comes from the lockfile, not the cache.
- New CLI binary: `skillpod` (entry point `skillpod.cli:app`).
- Specs added: `manifest`, `lockfile`, `source-resolver`,
  `registry-discovery`, `installer`, `cli`.

## Non-goals

- **Trust policy** (`allow_unverified`, `min_installs`, `min_stars`,
  `search`, `outdated`, `doctor`) — deferred to `add-skillpod-trust-and-search`
  (0.2.0).
- **Groups / `use:` / user_skills priority / `global` advisory CLI** —
  deferred to `add-skillpod-groups` (0.3.0).
- **Per-agent adapter / `copy` / `hardlink` install modes / Windows
  fallback** — deferred to `add-skillpod-adapter-layer` (0.4.0).
- **Schema freeze for v1** — Roadmap 1.0.0; out of scope.
- **Managing global skills content** — skillpod intentionally never
  modifies global skill directories.
