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
> One declarative manifest, multi-agent fan-out, switchable workspace profiles.

> **Pre-1.0 notice:** skillpod is under active development. The manifest, lockfile, and profile schema may change in breaking ways before the 1.0 schema freeze.

`skillpod` brings the `package.json` + lockfile workflow to AI agent skills.
Declare which skills your project depends on, lock them to a specific git
commit, then materialise them once into `.skillpod/skills/` and fan them out
to every agent you use — Claude Code, Codex, Gemini, Cursor, OpenCode,
Antigravity.

Need different skills for code review vs. frontend work? Define **workspace
profiles** and switch context per terminal, role, or project — no manifest
edits, no reinstalls. Each shell can run a different profile in parallel.

```
discover → resolve → lock → install → activate (profile)
```

---

## Why skillpod

| Pain                                | skillpod's answer                                        |
| ----------------------------------- | -------------------------------------------------------- |
| Global skills pollute every project | Project-scoped install under `.skillpod/`                |
| Agents drift from each other        | One source of truth → symlink/copy/hardlink fan-out      |
| "Works on my machine"               | `skillfile.lock` pins git commit + sha256                |
| Untrusted skills land silently      | Trust policy (`min_installs`, `min_stars`, `verified`)   |
| One huge skill set bleeds into every task | Workspace profiles filter skills/agents per role, session, or terminal |

> **skills.sh = discovery layer. skillpod = dependency system.**

---

## Prerequisites

- Python **3.11+**
- `git` installed and available in `$PATH` (required — used for all git source installs)
- Windows users: symlink mode requires Developer Mode or admin privileges; set `install.mode: copy` as a fallback

## Installation

```bash
pip install skillpod
# or
uv tool install skillpod
```

Requires Python **3.11+**.

Enable shell completion (bash, zsh, fish) by running `skillpod --install-completion` once after install.

---

## Quickstart

From an empty directory, run these four commands to go from nothing to a real skill directory fanned out into `.claude/skills/`:

```bash
# 1. Bootstrap a manifest (writes skillfile.yml + adds .skillpod/ to .gitignore)
skillpod init

# 2. Add a skill from a public repo — preview what's available first
skillpod add vercel-labs/agent-skills -l

# 3. Install a specific skill without interactive prompts
skillpod add vercel-labs/agent-skills -s web-design-guidelines -y

# 4. Confirm what landed
skillpod list
```

After step 3, the skill is in two places:

```
project/
├── skillfile.yml       ← declares sources, agents, and skills
├── skillfile.lock      ← pins each skill to a git commit + sha256
└── .skillpod/
    └── skills/
        └── web-design-guidelines/   ← real directory copy (survives cache clears)
.claude/skills/web-design-guidelines →  ../../.skillpod/skills/web-design-guidelines
```

`.skillpod/skills/` is the install root; `.claude/skills/` is the fan-out that your agent reads.

> **Tip:** Commit `skillfile.lock` alongside `skillfile.yml` so teammates and CI reproduce exactly the same skills.

### Adding skills from a git source

`skillpod add` accepts a **source identifier** and discovers `SKILL.md` files
inside it. The matching `sources:` entry is appended to `skillfile.yml`
automatically; no hand-editing required.

**Supported input formats:**

```bash
# 1. GitHub shorthand — expands to https://github.com/<owner>/<repo>
skillpod add vercel-labs/agent-skills -l

# 2. Full GitHub URL
skillpod add https://github.com/vercel-labs/agent-skills -l

# 3. Browser tree URL — installs only the targeted subdirectory as the source root
#    Works for GitHub (/tree/) and GitLab (/-/tree/)
skillpod add https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines -y

# 4. Any other git host (GitLab, Bitbucket, self-hosted, …)
skillpod add https://gitlab.com/org/repo -l

# 5. Any git URL — SSH SCP-style or full URL
skillpod add git@github.com:vercel-labs/agent-skills.git -l
skillpod add ssh://git@gitlab.com/org/repo.git -l

# 6. Local directory
skillpod add ./my-local-skills -l
skillpod add ~/shared/skills -l
```

**`--ref` interaction:**
- When no `--ref` is given, skillpod auto-detects the remote's default branch
  (works with `main`, `master`, or any custom default).
- A browser tree URL already encodes a ref (`/tree/<ref>/…`); `--ref` overrides it
  when you need to pin a different branch or commit.
- The resolved ref is written into `skillfile.yml` so reinstalls are reproducible.

**Common install patterns:**

```bash
# Preview skills in a source without installing
skillpod add anthropics/skills -l

# Install two specific skills
skillpod add anthropics/skills -s pdf -s docx -y

# Install every skill in the source
skillpod add anthropics/skills -s '*' -y

# Restrict fan-out to one declared agent
skillpod add anthropics/skills -s pdf -a claude -y

# Install globally to ~/.skillpod/skills/
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

Global profile files have their own schema at
[`schemas/global-profile.schema.json`](./schemas/global-profile.schema.json);
reproduce it with `skillpod schema --profile --output schemas/global-profile.schema.json`.

---

## Commands

| Command                     | What it does                                                             |
| --------------------------- | ------------------------------------------------------------------------ |
| `skillpod init`             | Bootstrap a new `skillfile.yml` in the current directory                 |
| `skillpod install`          | Install every skill declared in the manifest                             |
| `skillpod add`              | Add a skill to the manifest and install it                               |
| `skillpod remove`           | Remove a skill from the manifest and uninstall it                        |
| `skillpod list`             | List installed skills and their resolved sources                         |
| `skillpod sync`             | Re-create fan-out entries from the lockfile without re-resolving         |
| `skillpod search`           | Search the registry for skills matching a query                          |
| `skillpod outdated`         | Show which locked skills have drifted from upstream                      |
| `skillpod update`           | Re-resolve and refresh skills in the lockfile                            |
| `skillpod doctor`           | Verify manifest / lockfile / symlink consistency                         |
| `skillpod status`           | Show project status, active profile, and shell session depth             |
| `skillpod resolve`          | Resolve the effective skill set with optional profile filter and explain |
| `skillpod switch`           | Set the active profile; global scope reconciles & downloads skills (`--dry-run`, `--back`) |
| `skillpod shell <profile>`  | Start a sub-shell with a profile pre-activated                           |
| `skillpod profile`          | Manage workspace profiles (create, list, show, add, remove, diff, export, import, save) |
| `skillpod global`           | Manage global skills: list, link/unlink to agents, consolidate, audit   |
| `skillpod adapter`          | Inspect the active adapter registry                                      |

`--help` on any subcommand shows full options.

> **Machine-readable output / CI:** Most commands accept `--json` and print structured JSON to stdout. Use this for scripting, piping into `jq`, or integrating with CI pipelines — for example `skillpod list --json`, `skillpod status --json`, `skillpod global list --json`.

### `skillpod global list`

Lists skills in the canonical global install root (`~/.skillpod/skills/`).
The `LINKED` column shows which agents currently have a managed symlink pointing
to each skill.

```bash
skillpod global list           # default: ~/.skillpod/skills/ view
skillpod global list --agents  # per-agent view (~/.<agent>/skills/)
skillpod global list --json    # machine-readable
```

### `skillpod global link` / `skillpod global unlink`

Fan-out or remove agent symlinks for an already-installed global skill without
re-fetching from source.

| Invocation | Effect |
| --- | --- |
| `skillpod global link <name>` | Create symlinks in **all** known agent dirs |
| `skillpod global link <name> --agent codex --agent gemini` | Link to specific agents only |
| `skillpod global link <name> --yes` | Overwrite existing entries |
| `skillpod global unlink <name>` | Remove managed symlinks from all agents |
| `skillpod global unlink <name> --agent codex` | Remove managed symlink for one agent |

`unlink` only removes symlinks whose immediate target is `~/.skillpod/skills/<name>`.
Unmanaged entries (real directories or symlinks pointing elsewhere) are skipped with
a warning.

```bash
# link a skill to two agents
skillpod global link my-linter --agent claude --agent codex

# remove all agent links but keep the install root intact
skillpod global unlink my-linter
```

### `skillpod global archive`

Consolidates scattered global skills from agent directories
(`~/.<agent>/skills/<name>`) into the canonical location
`~/.skillpod/skills/<name>`.

| Invocation | Effect |
| --- | --- |
| `skillpod global archive` | Show usage help |
| `skillpod global archive '*'` | Archive **every** global skill at once |
| `skillpod global archive <name>` | Archive a single named skill |
| `skillpod global archive <n1> <n2> …` | Archive several named skills in one pass |

Skills that are already managed by skillpod — i.e. `~/.skillpod/skills/<name>` exists
and every agent copy is a symlink pointing there (installed via `skillpod add --global`) — are
**automatically skipped** in wildcard and multi-name modes and reported as `skipped_managed`
in `--json` output.

> **Shell note:** Quote the asterisk (`'*'`) or the shell will expand it to filenames in the
> current directory.

```bash
# archive every unmanaged global skill in one step
skillpod global archive '*'

# archive two specific skills
skillpod global archive my-linter code-review

# machine-readable output for scripting
skillpod global archive '*' --json
```

---

## Security model — what you're trusting

Adding a skill is like adding a dependency: you are pulling external code into your AI agent's context. Here is what skillpod does and does not gate for you.

**Registry trust policy (skills.sh only)**

The `registry.skills_sh` block in `skillfile.yml` (`allow_unverified`, `min_installs`, `min_stars`) is enforced **exclusively on results returned by the skills.sh registry** — i.e. when you run `skillpod search` or resolve a skill by bare name through the registry. The defaults are `allow_unverified: false`, `min_installs: 0`, `min_stars: 0`.

**git URL / `owner/repo` / local-path sources are not gated by this policy.** When you pass a URL, a GitHub shorthand, or a local directory directly to `skillpod add`, you are trusting that source directly — no install or star threshold is checked.

**What a skill can do**

A skill's `SKILL.md` file is read into your AI agent's context window as instructions. Review the source repo before adding a skill, the same way you would review a new package before `npm install`-ing it.

**Lockfile integrity**

Once a skill is installed, `skillfile.lock` pins its git commit SHA and a sha256 of its contents. Re-running `skillpod install` from the lockfile reproduces the exact same content — nothing can silently change underneath you. Run `skillpod doctor` to verify the current install matches the lock.

---

## Workspace Profiles (v0.6.x)

Workspace profiles let you switch your AI coding context without editing
`skillfile.yml`. A profile is a named filter that selects which skills and
agents are active for a given session, role, or project.

### Defining a profile

Add a `profiles:` block to `skillfile.yml`:

```yaml
profiles:
  reviewer:
    type: role
    skills: [code-review, audit]
    agents: [claude, codex]

  frontend:
    type: project
    skills: [react-patterns, css-audit]
    agents: [claude]
```

Create and manage profiles from the CLI:

```bash
skillpod profile create reviewer --type role
skillpod profile add reviewer code-review
skillpod profile add reviewer audit
skillpod profile list
skillpod profile show reviewer
```

### Activating a profile

**Per-command** (no persistent state):

```bash
skillpod resolve --profile reviewer
skillpod status --profile reviewer
```

**Project-scoped** (persists in `.skillpod/active-profile`):

```bash
skillpod switch reviewer                     # default: project scope
skillpod profile current                     # → reviewer (project)
```

**Global** — `switch --scope global` materialises a **global profile**
(`~/.skillpod/profiles/<name>.yml`): it reconciles the global skill set and
records the active profile in `~/.skillpod/active-profile`. This is its own
topic — see ["Global profiles that download & swap skills"](#global-profiles-that-download--swap-skills-switch---scope-global) below.

**Session-scoped** (env var only, no files written):

```bash
eval "$(skillpod switch reviewer --scope session)"
echo $SKILLPOD_ACTIVE_PROFILE   # → reviewer
```

Once a profile is active, all commands (`resolve`, `install`, `sync`, `status`)
automatically use it — no `--profile` flag needed.

### Global profiles that download & swap skills (`switch --scope global`)

The `profiles:` block above is a *filter* over a project's declared skills.
A **global profile** is the standalone counterpart: a self-contained file at
`~/.skillpod/profiles/<name>.yml` whose skills carry their own **source**, so it
works without any project. Switching to it reconciles your global per-agent
skill directories (`~/.<agent>/skills/`) to match the profile — downloading
anything missing and unlinking anything the profile dropped.

```yaml
# ~/.skillpod/profiles/developer.yml
version: 1
profile:
  name: developer                  # optional; used as the filename on URL download
  description: Core dev skills      # optional; shown in listings
  type: role
  skills:
    - audit                          # already installed: name only
    - name: polish                   # downloaded on switch from its source
      source: anthropics/skills      # git URL / owner/repo / local path
      ref: main                      # optional
      subpath: skills/polish         # optional
```

A profile is just a skill set — it does **not** record target agents. Choose
them at switch time with `--agent`/`-a` (repeatable); omit it to install to all
supported agents.

```bash
skillpod switch developer --scope global --dry-run        # preview the reconcile diff
skillpod switch developer --scope global                  # apply to all agents
skillpod switch developer --scope global -a claude -a codex   # apply to specific agents
skillpod switch --scope global --back                     # restore the previous global skill set
```

On switch (global scope), skillpod:

- **downloads** skills missing from `~/.skillpod/skills/` from their `source`
  (skills with no source that are not installed are skipped with a warning),
- **fans out** the profile's skills to the chosen agents (`--agent`, all by default),
- **unlinks** managed skills the profile no longer lists — keeping the
  `~/.skillpod/skills/` cache copy so re-activation needs no re-download,
- snapshots the previous set so `switch --back` can undo it,
- records the profile as the active global profile.

Switching to a different profile swaps the active global skill set. You can also
switch straight from a URL — downloaded to `~/.skillpod/profiles/` if not already
present:

```bash
skillpod switch https://example.com/developer.yml --scope global
skillpod switch owner/repo/profiles/developer.yml --scope global   # raw.githubusercontent shorthand
```

To capture your **current** global skills into a reusable profile (recovering
each skill's source where possible, so it is portable):

```bash
skillpod profile save developer
```

See `examples/developer.yml` (plus `designer.yml` and `project-manager.yml`).

### Sub-shell sessions (`skillpod shell`)

`skillpod shell <profile>` spawns `$SHELL` with the profile pre-activated.
Each terminal can run a different profile simultaneously:

```bash
# Terminal A
skillpod shell reviewer
echo $SKILLPOD_ACTIVE_PROFILE   # → reviewer
# PS1 is prefixed: [skillpod:reviewer] $

# Terminal B (simultaneously)
skillpod shell frontend
echo $SKILLPOD_ACTIVE_PROFILE   # → frontend
```

The parent shell's environment is never mutated. Exit the sub-shell to
return to the unfiltered context. Nesting (`skillpod shell` inside a
`skillpod shell`) is blocked — exit the inner shell first.

### Activation policy

Control how project and global profiles interact in `skillfile.yml`:

```yaml
activation:
  mode: strict           # strict | merge | fallback | manual (default)
  inherit_global: true   # set false to ignore ~/.skillpod/profiles/
  default_profile: reviewer  # activated automatically when no --profile is passed
```

| Mode       | Behaviour |
| ---------- | --------- |
| `manual`   | Profile applied only when explicitly requested; global profiles used as fallback |
| `strict`   | Only project-defined profiles accepted; global profiles blocked |
| `merge`    | Union of project + global skills and agents; project wins on conflict |
| `fallback` | Project profile first; falls back to global if not found in project |

### Profile composition

Combine profiles with `+` to activate the union of their skills and agents.
Composition works in two scopes:

```bash
# Session scope — env export, no files touched
eval "$(skillpod switch reviewer+frontend --scope session)"
skillpod resolve   # union of reviewer + frontend skills

# Global scope — download + fan out the combined set
skillpod switch dev+reviewer --scope global --agent claude
```

Operands must be **local profile names** (a `+URL` operand is rejected). Skills
union left-to-right, de-duplicated by name. When two operands declare the same
skill name with a **different source**, the **leftmost wins** and a warning is
printed. `--dry-run`, `--back`, and `--agent` all work with a composed switch.

### Resolution order

When more than one profile source could apply, skillpod resolves in this fixed
order (frozen as of v0.7.0):

```
CLI --profile  >  state active (session env > project file > global file)  >  activation.default_profile  >  none
```

A global profile file (`~/.skillpod/profiles/<name>.yml`) is the **source-bearing**
form — each skill may carry an inline `source`. For filter-mode resolution it
projects down to a name-only view, so one profile works both as a downloadable
skill set (`switch --scope global`) and as a read-time filter (`resolve --profile`).
Export the profile-file JSON Schema with `skillpod schema --profile`.

### Profile diff, export, and import

```bash
# Compare two profiles
skillpod profile diff reviewer frontend
# + code-review
# + audit
# - react-patterns
#   (common skills shown with indent)

# Export a profile to share with teammates
skillpod profile export reviewer --out reviewer.yml

# Import on another machine (or rename on import)
skillpod profile import reviewer.yml
skillpod profile import reviewer.yml --rename reviewer-strict --global
```

### Provenance (`--explain`)

```bash
skillpod resolve --profile reviewer --explain --json | jq .
```

Each skill in the output includes a `"layer"` field: `project`, `user_skill`,
`profile_filter`, or `global_profile_filter`.

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
| 0.5.5     | shipped     | `skillpod add owner/repo` auto-detects the remote's default branch (no longer hardcodes `main`) |
| 0.5.6     | shipped     | browser tree URL subpath support; `global archive` batch/wildcard mode; global add no longer fans out |
| 0.5.7     | shipped     | `global list` defaults to `~/.skillpod/skills/` view with LINKED column; new `global link` / `global unlink` / `--verbose` |
| 0.6.0     | shipped     | Workspace Profiles core — `profiles:` in manifest, `profile create/list/show/add/remove`, `resolve --profile` |
| 0.6.1     | shipped     | Project Isolation — `activation.mode` (strict/merge/fallback/manual), `inherit_global`, `default_profile` |
| 0.6.2     | shipped     | Safe Switching — `switch`, `profile use/current`, scoped state (`SKILLPOD_ACTIVE_PROFILE` env > project file > global file) |
| 0.6.3     | shipped     | Session Shell — `skillpod shell <profile>` spawns `$SHELL` with profile pre-activated, nest guard, PS1 prefix |
| 0.6.4     | shipped     | Composition Preview — `+` operator unions profiles; `profile diff/export/import` |
| 0.6.5     | shipped     | Global profile switch (download + fan-out + `--back`/URL/`save`); `--version`; shell completion; richer `add` output |
| 0.7.0     | planned     | Profile model beta — schema + resolver precedence + activation scope stable |
| 0.8.0     | planned     | Local-first visual management UI (`skillpod ui`)            |
| 1.0.0     | planned     | schema freeze                                               |

Full history: [`CHANGELOG.md`](./CHANGELOG.md).
Original design notes: [`plans/skillpod-plan.md`](./plans/skillpod-plan.md).

---

## Troubleshooting

**Agent directory is empty after `skillpod install`**
Ensure `agents:` is declared in `skillfile.yml`. The default is `[]`, which disables fan-out entirely.

**Symlink creation fails (Windows / CI)**
Set `install.mode: copy` in `skillfile.yml`, or add `fallback: [copy]` so copy is tried automatically when symlinks are denied.

**`global archive '*'` expands to filenames instead of running**
Quote the asterisk: `skillpod global archive '*'` — without quotes the shell expands `*` to files in the current directory.

**`skillpod add <owner/repo>` fails with a git error**
Ensure `git` is installed and in `$PATH`. For private repos, verify your SSH key or HTTPS credentials are configured.

**`skillfile.lock` hash mismatch / integrity error**
Run `skillpod doctor` to identify which skills are out of sync, then `skillpod update <name>` to re-resolve and repin.

**Cache is corrupted or taking too much disk space**
Clear `~/.cache/skillpod/` freely — it is a download buffer only. Installed skills under `.skillpod/skills/` are real directories and are unaffected.

**`skillpod install` vs `skillpod sync` — which do I need?**
- `install` — re-resolves sources and re-materialises skills; use after editing `skillfile.yml`
- `sync` — rebuilds fan-out entries from the existing lockfile without re-resolving; use after changing `agents:` or after a fresh clone

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
