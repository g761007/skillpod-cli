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

**Manage the skills your AI coding agents use — per project, or globally.**

A project says which skills it *recommends*. You decide what you actually run.
skillpod installs them once and wires them into every agent you use — Claude
Code, Codex, Gemini, Cursor, OpenCode, Antigravity.

> **Pre-1.0:** the manifest and profile schema may still change in breaking ways.

---

## Install

```bash
uv tool install skillpod     # or: pipx install skillpod
skillpod --version
```

Needs Python 3.11+ and `git` on your `PATH`.

---

## 60-second start

```bash
cd my-project
skillpod init                                   # writes skillfile.yml, gitignores .skillpod/
skillpod add anthropics/skills --skill pdf -y   # fetch a skill and wire it up
skillpod status                                 # confirm it landed
```

```
recommends: 1 skill(s)
  satisfied: 1   (1 project)
```

`pdf` is now materialised in `.skillpod/skills/` and linked into `.claude/skills/`,
so your agent can use it. Commit `skillfile.yml`; `.skillpod/` stays out of git.

Not sure what a repo offers? List before you commit to anything:

```bash
skillpod add anthropics/skills --list
```

---

## I want to…

### …recommend a set of skills for this project

`skillfile.yml` is the recommendation. Commit it, and a teammate who wants the
same setup runs one command.

```yaml
version: 1
agents: [claude]

sources:
  - name: skills
    type: git
    url: https://github.com/anthropics/skills
    ref: main
    subpath: skills

skills:
  - name: pdf
    source: skills
  - name: docx
    source: skills
```

```bash
skillpod install
```

Nothing here is enforced. A teammate who ignores it, or already has these
skills globally, is not doing anything wrong — see the next entry.

### …not install a skill I already have globally

This is the default. If a skill is already in `~/.skillpod/skills/`, the
recommendation is already met, so no project copy is made:

```console
$ skillpod install
Already present: 2 skill(s)
Satisfied by your global install: xlsx
```

It applies only where **every** agent you declare is known to read its personal
*and* project skill directories together. Verified today: **Claude Code,
Codex, and Gemini CLI**. Declare any other agent and that project gets a real
copy instead — an unverified agent is assumed *not* to merge, because a
silently missing skill is far worse than a redundant copy.

To force a project-local copy anyway:

```yaml
install:
  prefer_global: false
```

The three verified agents each resolve a name collision differently, so
`skillpod install` warns only where the project copy really is ignored:

| Agent | Same skill name in both places |
|---|---|
| Claude Code | the **personal** copy wins ([docs](https://code.claude.com/docs/en/skills)) — so `prefer_global: false` warns you the project copy is not the one in use |
| Gemini CLI | the **project** copy wins |
| Codex | neither — both appear in the skill selector |

### …see what I actually have right now

```console
$ skillpod status
project:    my-project
manifest:   /path/to/skillfile.yml

recommends: 4 skill(s)
  satisfied: 2   (1 global, 1 project)
  missing:   1   → skillpod install
  broken:    1   → skillpod doctor
```

Every count names the command that fixes it. For the per-skill breakdown:

```console
$ skillpod list
NAME      SOURCE    LAYER     INSTALLED
pdf       skills    project   fa0fa64bdc96
docx      skills    project   fa0fa64bdc96
```

`LAYER` says which copy is actually serving each skill: `project`, `global`,
`user`, `missing`, or `broken`.

### …install a skill for every project, not just this one

```bash
skillpod add anthropics/skills --skill xlsx -g -y
```

This puts the skill in `~/.skillpod/skills/` **without** wiring it into any
agent — that is a deliberate second step, so a global install never silently
changes what your agents see:

```bash
skillpod global link xlsx --agent claude    # or omit --agent for all of them
skillpod global list
```

```
NAME  LINKED     SIZE  MTIME
xlsx  cl      1102893  2026-07-21
```

### …turn a skill off without deleting it

```bash
skillpod unlink audit             # this project
skillpod unlink xlsx -g           # globally
```

The materialised copy stays put, so `skillpod link audit` brings it back with
no download. Only skillpod-created links are removed — anything you placed by
hand is reported and left alone.

This is deliberately not `remove`: that deletes the content and edits
`skillfile.yml`, which is much more than "stop showing me this".

### …use a skill I already have, in a project that doesn't declare it

```console
$ skillpod link xlsx
Copied 'xlsx' from ~/.skillpod/skills/ — nothing downloaded.
Linked to: claude
```

`link` never fetches. If the skill is already on your machine — in this project
or globally — it wires it up; if it is nowhere, it tells you to run
`skillpod add`.

### …update my global skills

```console
$ skillpod global update --dry-run
Would update 18 skill(s):
  algorithmic-art              5128e1865d67 → fa0fa64bdc96
  brand-guidelines             5128e1865d67 → fa0fa64bdc96
  …
  local        33 skill(s) — no upstream to pull from
  no source    37 skill(s) — origin unknown, reinstall from a source to make them updatable
```

Drop `--dry-run` to apply, or name specific skills:

```bash
skillpod global update pdf docx
```

Skills with no recoverable origin, skills from local directories, and remotes
that cannot be reached are reported and skipped — never fatal. One dead remote
does not stop the rest.

### …run only some of this project's skills right now

```console
$ skillpod switch minimal
active profile set to 'minimal' (scope: project)
  hidden: polish (still installed — switching back is instant)
```

Declare the subsets in `skillfile.yml`:

```yaml
profiles:
  minimal:
    skills: [audit]
```

Hidden skills stay in `.skillpod/skills/`, so switching back is offline and
immediate. `install` and `sync` respect the active profile too — neither will
put a hidden skill back.

### …switch my whole global setup at once

Save what you have now, then move between named sets:

```bash
skillpod profile save writing            # snapshot the current global skills
skillpod switch reviewing --scope global # download what's missing, unlink the rest
skillpod switch --back                   # undo
```

Add `--dry-run` to preview the reconcile first, or `dev+reviewer` to union two
profiles.

### …use a skill that only exists on my machine

Drop it in `.skillpod/user_skills/<name>/` and run `skillpod install`. It needs
no source and no manifest entry, and it takes precedence over a declared skill
of the same name.

---

## Commands

| Command | What it does |
| --- | --- |
| `skillpod init` | Write a starter `skillfile.yml` and gitignore `.skillpod/` |
| `skillpod add <source>` | Fetch a skill from a repo or directory and install it |
| `skillpod install` | Install what the manifest recommends and is not already present |
| `skillpod update [skill]` | Re-resolve and pull newer upstream content |
| `skillpod remove <skill>` | Drop a skill from the manifest and uninstall it |
| `skillpod link <skill>` | Make a skill visible to your agents (`-g` for global) |
| `skillpod unlink <skill>` | Hide it again, keeping the copy (`-g` for global) |
| `skillpod status` | The one-screen answer to "is this project ready" |
| `skillpod list` | Per-skill breakdown: source, layer, installed commit |
| `skillpod doctor` | Report faults with paths and codes |
| `skillpod sync` | Rebuild fan-out from the install record, offline |
| `skillpod outdated` | Compare installed commits against upstream |
| `skillpod search <query>` | Search the skills.sh registry |
| `skillpod global …` | `list`, `link`, `unlink`, `update`, `archive`, `doctor` |
| `skillpod profile …` | `create`, `list`, `show`, `save`, `diff`, `export`, `import` |
| `skillpod switch <name>` | Set the active profile for a scope |
| `skillpod shell <name>` | Sub-shell with a profile pre-activated |
| `skillpod resolve` | Show the effective skill set, with `--explain` |
| `skillpod adapter list` | Inspect the active adapter registry |
| `skillpod schema` | Emit the JSON Schema for editor integration |

`--help` on any subcommand shows the full options. Most commands accept
`--json` for scripting.

---

## `skillfile.yml` reference

Only `version` is required. Everything below shows its default.

```yaml
version: 1

# Agents that receive fan-out. Empty means skills land in .skillpod/skills/
# only. Supported: claude, codex, gemini, cursor, opencode, antigravity.
agents: [claude]

install:
  mode: symlink          # symlink | copy | hardlink
  fallback: [copy]       # tried when `mode` fails (e.g. symlinks denied)
  on_missing: error      # error | skip
  prefer_global: true    # a skill already in ~/.skillpod/skills/ counts as satisfied

sources:
  - name: skills
    type: git            # git | local
    url: https://github.com/anthropics/skills
    ref: main            # branch, tag, or commit
    subpath: skills      # git only — where the skills live inside the repo
    priority: 50         # higher wins when several sources could provide a skill

skills:
  - audit                          # shorthand: resolve against sources, then the registry
  - name: pdf
    source: skills                 # pin to one source, skipping the registry
    version: <40-char commit sha>  # optional: pin to an exact commit

groups:                  # named bundles, activated by `use:`
  frontend: [pdf, docx]
use: [frontend]

registry:
  default: skills.sh
  skills_sh:
    allow_unverified: false
    min_installs: 0
    min_stars: 0

profiles:                # named subsets, see `skillpod switch`
  minimal:
    skills: [pdf]

activation:
  mode: manual           # manual | strict | merge | fallback
  inherit_global: true
  default_profile: null
```

Run `skillpod schema --output schemas/skillfile.schema.json` for editor
autocomplete, or `skillpod schema --profile` for the global profile schema.

---

## How it works

```
skillfile.yml  →  resolve  →  cache  →  .skillpod/skills/  →  .<agent>/skills/
```

1. **Resolve.** A skill declared with `source:` is looked up there. A bare name
   probes declared sources by priority, then falls back to the skills.sh
   registry.
2. **Cache.** Git sources clone into `~/.cache/skillpod/<host>/<owner>/<repo>@<commit>/`,
   written by atomic rename so a partial clone is never visible.
3. **Materialise.** `.skillpod/skills/<name>/` is a real directory copy, never
   a symlink — clearing the cache cannot break an installed project.
4. **Fan out.** Each declared agent gets `.<agent>/skills/<name>` pointing at
   that copy, using `install.mode`.

**What gets recorded.** `.skillpod/installed.yml` (and `~/.skillpod/installed.yml`
for global installs) records what is on this machine: source, ref, commit,
content digest. Both live under `.skillpod/`, which is gitignored — they
*describe* your machine, they do not constrain a teammate's.

**`install` versus `update`.** `install` brings in what is missing and leaves
alone what is already there, so re-running it is offline and instant. Pulling
newer upstream content is `skillpod update` — always an explicit act, never a
side effect.

---

## Security model — what you're trusting

Adding a skill pulls external text into your agent's context. A `SKILL.md` is
read as *instructions*, so review a repo before adding it, the same way you
would review a package before installing it.

**The registry trust policy gates skills.sh only.** `registry.skills_sh`
(`allow_unverified`, `min_installs`, `min_stars`) applies when you `search` or
resolve a bare name through the registry. Passing a git URL, an `owner/repo`
shorthand, or a local path to `skillpod add` trusts that source directly — no
threshold is checked.

**Content is digested, not policed.** Each install records a sha256 of what it
materialised, so `skillpod doctor` can tell you the disk no longer matches the
record. That detects drift and corruption; it does not vet the content.

---

## Roadmap

| Milestone | Status | Highlights |
| --- | --- | --- |
| 0.1.0 – 0.5.x | shipped | manifest, installer, registry, adapters, `global` CLI |
| 0.6.x | shipped | workspace profiles, activation policy, session shell, composition |
| 0.9.0 | shipped | **recommendation model** — `skillfile.lock` retired, `prefer_global`, `global update`, `status` dashboard, unified `link`/`unlink`, project profiles that reconcile fan-out |
| 1.0.0 | planned | schema freeze |

Full history: [`CHANGELOG.md`](./CHANGELOG.md).

---

## Troubleshooting

**Agent directory is empty after `install`**
`agents:` defaults to `[]`, which disables fan-out. Declare the agents you use.

**A skill is installed but my agent ignores it**
If the same name exists in `~/.skillpod/skills/`, Claude Code prefers the
personal copy. `skillpod status` shows which layer is serving it.

**Symlink creation fails (Windows, some CI)**
Set `install.mode: copy`, or rely on the default `fallback: [copy]`.

**`skillpod add <owner/repo>` fails with a git error**
Check `git` is on `$PATH`. For private repos, verify your SSH or HTTPS
credentials.

**`global archive '*'` expands to filenames**
Quote the asterisk — the shell expands it otherwise.

---

## Contributing

```bash
uv sync
uv run pytest -q
uv run ruff check src tests
uv run mypy src/skillpod
```

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for the module map and conventions.

## License

MIT — see [`LICENSE`](./LICENSE).
