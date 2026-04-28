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
  projects.
- **Fan out** — one entry per agent in `agents:`, materialised by an
  `Adapter` (default: identity). Mode is `symlink | copy | hardlink` with a
  configurable fallback chain for hosts that disallow the primary mode.

---

## `skillfile.yml`

A real manifest looks like this (see [`examples/skillfile.yml`](./examples/skillfile.yml)):

```yaml
version: 1

registry:
  default: skills.sh
  skills.sh:
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

User-only skills (not committed to the manifest) live under
`.skillpod/user_skills/` and take priority over project-declared skills with
the same name.

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
| `skillpod global`    | Inspect global agent skill directories (advisory only)                   |
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
| **0.5.0** | **current** | first public PyPI release + packaging hardening             |
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
