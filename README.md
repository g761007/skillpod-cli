<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/g761007/skillpod-cli/main/docs/assets/banner-dark.png">
    <img src="https://raw.githubusercontent.com/g761007/skillpod-cli/main/docs/assets/banner.png" alt="skillpod — pod-style dependency manager for AI coding agent skills">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/g761007/skillpod-cli/actions/workflows/ci.yml"><img src="https://github.com/g761007/skillpod-cli/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <a href="https://pypi.org/project/skillpod/"><img src="https://img.shields.io/pypi/v/skillpod.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/skillpod/"><img src="https://img.shields.io/pypi/pyversions/skillpod.svg" alt="Python"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
</p>

> **Pod-style dependency manager for AI coding agent skills.**
> One declarative manifest, multi-agent fan-out.

`skillpod` brings the `package.json` + lockfile workflow to AI agent skills.
Declare which skills your project depends on, lock them to a specific git
commit, then materialise them once into `.skillpod/skills/` and fan them out
to every agent you use — Claude Code, Codex, Gemini, Cursor, OpenCode,
Antigravity.

```
discover → resolve → lock → install
```

---

## Why skillpod

| Pain                                | skillpod's answer                                        |
| ----------------------------------- | -------------------------------------------------------- |
| Global skills pollute every project | Project-scoped install under `.skillpod/`                |
| Agents drift from each other        | One source of truth → symlink/copy/hardlink fan-out      |
| "Works on my machine"               | `skillfile.lock` pins git commit + sha256                |
| Untrusted skills land silently      | Trust policy (`min_installs`, `min_stars`, `verified`)   |

> **skills.sh = discovery layer. skillpod = dependency system.**

---

## Installation

```bash
pip install skillpod
# or
uv tool install skillpod
```

Requires Python **3.11+**.

---

## Quickstart

```bash
# 1. Bootstrap a manifest in the current project
skillpod init

# 2. Add a skill (resolves through skills.sh by default)
skillpod add audit

# 3. Install everything declared in skillfile.yml
skillpod install

# 4. Inspect what landed where
skillpod list
```

### Adding skills from a git source

`skillpod add` also accepts a **source identifier** — a git URL, GitHub
`owner/repo` shorthand, or local path — and discovers `SKILL.md` files
inside it. The matching `sources:` entry is appended to `skillfile.yml`
automatically; no hand-editing required.

```bash
# Preview the skills exposed by a repository
skillpod add anthropics/skills -l

# Install two skills from that source into the current project
skillpod add anthropics/skills -s pdf -s docx -y

# `*` selects every skill in the source
skillpod add anthropics/skills -s '*' -y

# Restrict fan-out to one declared agent (manifest agents stay untouched)
skillpod add anthropics/skills -s pdf -a claude -y

# Install globally to ~/.skillpod/skills/ only
skillpod add anthropics/skills -s pdf -g -y
```

Flags: `-s/--skill` selects one or more skills (`*` means all),
`-a/--agent` filters target agents in project mode, `-l/--list` previews
without installing, `-g/--global` installs to `~/.skillpod/skills/`
instead of the project, `-y/--yes` skips interactive prompts and replaces
existing global entries, `--ref` pins a git ref/branch/commit, `--source-name`
overrides the auto-derived source name written to the manifest.

After `skillpod install`, the same skill is reachable from every agent you
declared:

```
project/
├── skillfile.yml
├── skillfile.lock
├── .skillpod/
│   └── skills/
│       └── audit/
└── .claude/skills/audit  →  ../../.skillpod/skills/audit
    .codex/skills/audit   →  ../../.skillpod/skills/audit
    .gemini/skills/audit  →  ../../.skillpod/skills/audit
```

---

## How it works

```
skills.sh           git repo               .skillpod/skills           agents
(discovery)   →   (immutable commit)  →   (project install)   →   (symlink fan-out)
```

- **Discover** — `skillpod search <query>` queries skills.sh. Trust policy
  filters out unverified or low-signal entries.
- **Resolve** — every install pins a git commit + sha256 into `skillfile.lock`.
- **Cache** — bare clones land in `~/.cache/skillpod/` and are reused across
  projects. The cache is a download buffer; clearing it never breaks an
  installed skill.
- **Materialise** — `.skillpod/skills/<name>/` (project) and
  `~/.skillpod/skills/<name>/` (global) are **real directories** copied
  from the source. Re-running install is hash-idempotent.
- **Fan out** — one entry per agent in `agents:`, materialised by an
  `Adapter` (default: identity). Mode is `symlink | copy | hardlink` with a
  configurable fallback chain for hosts that disallow the primary mode.
  Default `symlink` fan-out points at the real install root, so cache
  pruning is always safe.

---

## `skillfile.yml`

A real manifest looks like this (see [`examples/skillfile.yml`](./examples/skillfile.yml)
for a fully-annotated reference):

```yaml
version: 1

registry:
  default: skills.sh
  skills_sh:
    allow_unverified: false
    min_installs: 1000
    min_stars: 50

agents:
  - claude
  - codex
  - gemini

install:
  mode: symlink
  fallback: [copy]
  on_missing: error

sources:
  - name: anthropic
    type: git
    url: https://github.com/anthropics/skills
    ref: main
    priority: 80

skills:
  - audit
  - polish
  - name: custom-skill
    source: anthropic

groups:
  frontend:
    - audit
    - web-design

use:
  - frontend
```

### Field reference

The minimal valid manifest is `version: 1` plus at least one source of
skills (`skills:`, `groups:`+`use:`, or a directory under
`.skillpod/user_skills/`). Every other field has a deterministic default.

#### Top-level

| Field      | Required | Type                    | Default      | Notes                                                                 |
| ---------- | -------- | ----------------------- | ------------ | --------------------------------------------------------------------- |
| `version`  | **yes**  | int                     | —            | Schema version. Must be `1`.                                          |
| `registry` | no       | mapping                 | see below    | Registry resolver configuration.                                      |
| `agents`   | no       | list[str \| object]     | `[]`         | Targets for fan-out. Empty list disables fan-out.                     |
| `install`  | no       | mapping                 | see below    | How fan-out entries are materialised.                                 |
| `sources`  | no       | list[object]            | `[]`         | Additional skill sources beyond the registry.                         |
| `skills`   | no       | list[str \| object]     | `[]`         | Skills to install (shorthand string or object form).                  |
| `groups`   | no       | mapping[str → list]     | `{}`         | Named bundles of skill entries.                                       |
| `use`      | no       | list[str]               | `[]`         | Group names whose members join the effective skill set.               |

Unknown top-level keys are rejected — typos surface immediately.

#### `registry`

| Field                          | Required | Type | Default       |
| ------------------------------ | -------- | ---- | ------------- |
| `default`                      | no       | str  | `"skills.sh"` |
| `skills_sh.allow_unverified`   | no       | bool | `false`       |
| `skills_sh.min_installs`       | no       | int  | `0`           |
| `skills_sh.min_stars`          | no       | int  | `0`           |

#### `agents[]`

Two accepted shapes:

- Bare string: `- claude`
- Object form:

  | Field     | Required | Type | Default | Notes                                                          |
  | --------- | -------- | ---- | ------- | -------------------------------------------------------------- |
  | `name`    | **yes**  | str  | —       | One of `claude`, `codex`, `gemini`, `cursor`, `opencode`, `antigravity`. |
  | `adapter` | no       | str  | `null`  | Dotted path to a custom adapter class.                          |

#### `install`

| Field        | Required | Type                                | Default     | Notes                                                       |
| ------------ | -------- | ----------------------------------- | ----------- | ----------------------------------------------------------- |
| `mode`       | no       | `symlink` \| `copy` \| `hardlink`   | `"symlink"` | Primary materialisation mode for **agent fan-out** (`.<agent>/skills/`). The install root `.skillpod/skills/<name>/` is always a real-directory copy. |
| `on_missing` | no       | `error` \| `skip`                   | `"error"`   | Behaviour when a declared skill cannot be resolved.         |
| `fallback`   | no       | list of mode literals               | `["copy"]`  | Tried in order when `mode` fails (e.g. OS denies symlinks). |

#### `sources[]`

| Field      | Required                          | Type                | Default  | Notes                                                |
| ---------- | --------------------------------- | ------------------- | -------- | ---------------------------------------------------- |
| `name`     | **yes**                           | str                 | —        | Unique identifier referenced by `skills[].source`.   |
| `type`     | **yes**                           | `local` \| `git`    | —        | Selects which of `path` / `url` is required.         |
| `path`     | **yes** when `type: local`        | str                 | —        | Filesystem path. Forbidden when `type: git`.         |
| `url`      | **yes** when `type: git`          | str                 | —        | Git URL. Forbidden when `type: local`.               |
| `ref`      | no (only meaningful for `git`)    | str                 | `"main"` | Branch, tag, or commit-ish.                          |
| `priority` | no                                | int                 | `50`     | Higher wins when shorthand names match in multiple sources. |

#### `skills[]`

Two accepted shapes:

- Shorthand string: `- audit` (resolved against `sources` in priority order, then the registry)
- Object form:

  | Field     | Required | Type | Default | Notes                                                            |
  | --------- | -------- | ---- | ------- | ---------------------------------------------------------------- |
  | `name`    | **yes**  | str  | —       | Skill identifier.                                                |
  | `source`  | no       | str  | `null`  | Must match a declared `sources[].name`.                          |
  | `version` | no       | str  | `null`  | Commit-ish; resolved and pinned in `skillfile.lock` at install time. |

#### `groups` and `use`

`groups` is a mapping of group name → list of skill entries (same shorthand
/ object forms as `skills`). `use` is a list of group names; every entry
must reference a declared group. Group names must not collide with any
name in `skills`.

User-only skills (not committed to the manifest) live under
`.skillpod/user_skills/` and take priority over project-declared skills
with the same name.

### JSON Schema

`skillfile.yml` has a generated JSON Schema at
[`schemas/skillfile.schema.json`](./schemas/skillfile.schema.json), produced
from the pydantic manifest models. Reproduce it with
`skillpod schema --output schemas/skillfile.schema.json`. VS Code and JetBrains
IDEs can use this schema for autocomplete and validation.

---

## Commands

| Command              | What it does                                                             |
| -------------------- | ------------------------------------------------------------------------ |
| `skillpod init`      | Bootstrap a new `skillfile.yml` in the current directory                 |
| `skillpod install`   | Install every skill declared in the manifest                             |
| `skillpod add`       | Add a skill to the manifest and install it                               |
| `skillpod remove`    | Remove a skill from the manifest and uninstall it                        |
| `skillpod list`      | List installed skills and their resolved sources                         |
| `skillpod sync`      | Re-create fan-out entries from the lockfile without re-resolving         |
| `skillpod search`    | Search the registry for skills matching a query                          |
| `skillpod outdated`  | Show which locked skills have drifted from upstream                      |
| `skillpod update`    | Re-resolve and refresh skills in the lockfile                            |
| `skillpod doctor`    | Verify manifest / lockfile / symlink consistency                         |
| `skillpod global`    | Inspect, consolidate, or audit global agent skill directories            |
| `skillpod adapter`   | Inspect the active adapter registry                                      |

`--help` on any subcommand shows full options. `--json` produces
machine-readable output where it makes sense.

---

## Roadmap & status

| Milestone | Status      | Highlights                                                  |
| --------- | ----------- | ----------------------------------------------------------- |
| 0.1.0     | shipped     | manifest, lockfile, installer, registry resolution          |
| 0.2.0     | shipped     | trust policy, `search`, `outdated`, `doctor`                |
| 0.3.0     | shipped     | groups, user_skills, advisory `global` CLI                  |
| 0.4.0     | shipped     | adapter layer, copy/hardlink modes, per-agent `sync`        |
| 0.5.0     | shipped     | first public PyPI release + packaging hardening             |
| 0.5.1     | shipped     | source-mode `skillpod add`, schema drift guard              |
| 0.5.2     | shipped     | `global archive` consolidates skills into `~/.skillpod/skills` |
| 0.5.3     | shipped     | install root materialised as real-directory copy (cache-prune safe) |
| 0.5.4     | shipped     | `skillpod add owner/repo` supports single-skill repos with `SKILL.md` at the root |
| **0.5.5** | **current** | `skillpod add owner/repo` auto-detects the remote's default branch (no longer hardcodes `main`) |
| 1.0.0     | planned     | schema freeze                                               |

Full history: [`CHANGELOG.md`](./CHANGELOG.md).
Original design notes: [`plans/skillpod-plan.md`](./plans/skillpod-plan.md).
Specs: [`openspec/specs/`](./openspec/specs/).

---

## Contributing

```bash
git clone https://github.com/g761007/skillpod-cli.git
cd skillpod-cli
uv sync
uv run pytest -q
uv run ruff check src tests
uv run mypy src/skillpod
```

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the full PR / OpenSpec workflow,
and [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md) for community expectations.
Security reports: [`SECURITY.md`](./SECURITY.md).

---

## License

MIT — see [`LICENSE`](./LICENSE).
