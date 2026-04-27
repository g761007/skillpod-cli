# cli Specification

## Purpose
TBD - created by archiving change add-skillpod-mvp-install. Update Purpose after archive.
## Requirements
### Requirement: `skillpod init` bootstraps a project

The system SHALL provide a `skillpod init` subcommand that, when run in a
directory without an existing `skillfile.yml`, creates a minimal valid
manifest containing `version: 1`, an empty `skills: []`, and a default
`agents:` list, and SHALL append `.skillpod/` to `.gitignore` when that
file is writable.

#### Scenario: Fresh `init`

- **GIVEN** a directory with no `skillfile.yml`
- **WHEN** the user runs `skillpod init`
- **THEN** `skillfile.yml` SHALL exist with `version: 1` and an empty
  `skills:` list, and `.gitignore` SHALL contain a `.skillpod/` entry if
  it did not already

#### Scenario: Re-running `init` is safe

- **GIVEN** a directory that already contains `skillfile.yml`
- **WHEN** the user runs `skillpod init` again
- **THEN** the command SHALL exit with a non-zero status and SHALL NOT
  overwrite the existing manifest

### Requirement: Core install commands

The system SHALL expose `skillpod install`, `skillpod add <skill>`,
`skillpod remove <skill>`, `skillpod list`, and `skillpod sync`, each
delegating to the installer pipeline as appropriate. Failures in the
pipeline SHALL surface as non-zero exit codes.

#### Scenario: `add` updates manifest and lockfile atomically

- **WHEN** the user runs `skillpod add audit`
- **THEN** the command SHALL append `audit` to `skillfile.yml`, run the
  install pipeline, refresh `skillfile.lock`, and exit `0`; if any step
  fails, both files SHALL be left unchanged from before the run

#### Scenario: `remove` deletes materialised state

- **WHEN** the user runs `skillpod remove audit` after a prior install
- **THEN** the command SHALL drop `audit` from `skillfile.yml`, delete
  `.skillpod/skills/audit`, delete each `.<agent>/skills/audit` symlink
  managed by skillpod, and refresh `skillfile.lock`

#### Scenario: `sync` is idempotent against the lockfile

- **GIVEN** `.skillpod/skills/` is empty but `skillfile.lock` is
  populated
- **WHEN** the user runs `skillpod sync`
- **THEN** the command SHALL re-create symlinks under `.skillpod/skills`
  and each agent target without re-resolving against the registry, and
  running it twice in a row SHALL produce no diff after the first run

### Requirement: Global options `--manifest` and `--json`

The system SHALL accept the global options `--manifest <path>` (override
the manifest location, default `./skillfile.yml`) and `--json` (emit
machine-readable JSON instead of human-readable output) on every
subcommand introduced in this change.

#### Scenario: Custom manifest path

- **WHEN** the user runs
  `skillpod install --manifest ./examples/skillfile.yml`
- **THEN** the install pipeline SHALL read the manifest from that path
  rather than from `./skillfile.yml`

#### Scenario: JSON output for `list`

- **WHEN** the user runs `skillpod list --json`
- **THEN** stdout SHALL be a single JSON document parseable by
  `json.loads`, with no surrounding human-readable formatting

### Requirement: Stable exit codes

The system SHALL use exit code `0` for success, `1` for user-visible
errors (manifest invalid, conflicting symlinks, frozen-mode drift), and
`2` for system or network errors (registry unreachable, git failure,
filesystem permission denied).

#### Scenario: Registry timeout returns code 2

- **GIVEN** the registry is unreachable
- **WHEN** `skillpod install` requires it and aborts
- **THEN** the process SHALL exit with status `2`

#### Scenario: Manifest validation failure returns code 1

- **GIVEN** `skillfile.yml` declares an unknown agent
- **WHEN** the user runs `skillpod install`
- **THEN** the process SHALL exit with status `1`

### Requirement: `skillpod search` discovers registry skills

The system SHALL provide a `skillpod search <query>` subcommand that
queries the registry for skills matching `<query>`, renders the matches
in a stable column order (`name`, `repo`, `installs`, `stars`,
`verified`, `passes-policy`), and supports `--limit <n>` (default `20`)
and `--json` for machine-readable output.

#### Scenario: Search shows policy-pass badge

- **GIVEN** the active manifest enforces
  `min_installs: 1000, min_stars: 50, allow_unverified: false`
- **AND** the registry returns three results: A (verified, 5000
  installs, 200 stars), B (verified, 12 installs, 1 star), C
  (unverified, 1 install, 0 stars)
- **WHEN** the user runs `skillpod search audit`
- **THEN** all three rows SHALL appear, with `passes-policy` `true` for
  A and `false` for B and C; the command SHALL exit `0`

#### Scenario: Search JSON output

- **WHEN** the user runs `skillpod search audit --json`
- **THEN** stdout SHALL be a single JSON document of the form
  `{ "query": "audit", "results": [ { "name": ..., "repo": ...,
  "installs": ..., "stars": ..., "verified": ..., "passes_policy": ... }, ... ] }`

### Requirement: `skillpod outdated` reports lockfile drift

The system SHALL provide a `skillpod outdated` subcommand that, for each
entry in `skillfile.lock`, fetches the current latest commit
(through the registry for registry-resolved skills, or via
`git ls-remote` for explicit git sources) and reports per-skill drift.

#### Scenario: One skill drifted

- **GIVEN** `skillfile.lock` has `audit -> commit abc123…` and the
  upstream now points at `def456…`
- **WHEN** the user runs `skillpod outdated`
- **THEN** stdout SHALL report a row showing `audit | abc123 | def456`
  and the command SHALL exit `0`

#### Scenario: Outdated handles network failure

- **GIVEN** the registry is unreachable
- **WHEN** the user runs `skillpod outdated`
- **THEN** the command SHALL exit `2` and surface the underlying error,
  without partially printing rows

### Requirement: `skillpod update` refreshes the lockfile

The system SHALL provide a `skillpod update [skill]` subcommand that
re-runs the install pipeline in a "force re-resolve" mode. When invoked
with a name, only that skill SHALL be updated; without arguments, every
manifest skill SHALL be refreshed. Trust policy SHALL still be enforced
on the new resolution result.

#### Scenario: Update single skill

- **WHEN** the user runs `skillpod update audit`
- **THEN** the command SHALL re-resolve only `audit`, refresh its
  lockfile entry, leave other lockfile entries untouched, and exit `0`

#### Scenario: Update aborts on trust failure

- **GIVEN** a previously trusted `audit` was downgraded by the registry
  to `verified: false`
- **AND** the policy still requires `allow_unverified: false`
- **WHEN** `skillpod update audit` runs
- **THEN** the command SHALL raise `TrustError`, exit `1`, and SHALL
  NOT modify `skillfile.lock` or `.skillpod/skills/audit`

### Requirement: `skillpod doctor` verifies project consistency

The system SHALL provide a `skillpod doctor` subcommand that performs
each of the following checks and reports findings with severity
`error` or `warning`:

1. Every manifest skill exists in `skillfile.lock` (or is local-sourced).
2. Every lockfile entry has a materialised directory at
   `.skillpod/skills/<name>/`.
3. Every `.<agent>/skills/<name>` symlink declared by the manifest
   resolves into `.skillpod/skills/`.
4. No directory exists under `.skillpod/skills/` that is not referenced
   by the manifest.

The command SHALL exit `0` when no findings have severity `error`,
`1` otherwise, and `2` if the filesystem cannot be read.

#### Scenario: Clean project

- **GIVEN** a project that has just successfully run `skillpod install`
- **WHEN** the user runs `skillpod doctor`
- **THEN** the command SHALL print a "no findings" summary and exit
  `0`

#### Scenario: Broken symlink detected

- **GIVEN** a project where `.claude/skills/audit` points at a path that
  no longer exists
- **WHEN** the user runs `skillpod doctor`
- **THEN** the command SHALL emit an `error`-severity finding referring
  to that symlink and exit `1`

#### Scenario: Orphan directory under .skillpod/skills

- **GIVEN** `.skillpod/skills/legacy/` exists but `legacy` is not in
  the manifest
- **WHEN** the user runs `skillpod doctor`
- **THEN** the command SHALL emit a `warning`-severity finding listing
  the orphan directory; without other errors, it SHALL still exit `0`

### Requirement: `skillpod global list` enumerates global skills

The system SHALL provide a `skillpod global list` subcommand that scans
known global agent skill directories under `$HOME` (`~/.claude/skills/`,
`~/.codex/skills/`, `~/.gemini/skills/`, `~/.cursor/skills/`,
`~/.opencode/skills/`, `~/.antigravity/skills/`) and prints each
discovered skill with its agent, size, and last-modified time. The
command SHALL NOT modify any of those directories.

#### Scenario: Lists skills across two agents

- **GIVEN** `~/.claude/skills/audit/` and `~/.codex/skills/polish/`
  exist
- **WHEN** the user runs `skillpod global list`
- **THEN** the command SHALL emit a row for `audit` (claude) and a row
  for `polish` (codex), and SHALL NOT touch either directory

#### Scenario: JSON output

- **WHEN** the user runs `skillpod global list --json`
- **THEN** stdout SHALL be a JSON array of objects with stable keys
  `agent`, `name`, `path`, `size_bytes`, `mtime`

### Requirement: `skillpod global archive` is non-destructive

The system SHALL provide a `skillpod global archive <skill>` subcommand
that renames every matching global skill directory to
`<original>.archived-YYYYMMDD-HHMMSS` (UTC). The command SHALL NEVER
delete files, and SHALL refuse to act on any path that resolves inside
the current project working tree.

#### Scenario: Archive renames the global skill

- **GIVEN** `~/.claude/skills/audit/` exists
- **WHEN** the user runs `skillpod global archive audit` at
  `2026-04-27T15:00:00Z`
- **THEN** the directory SHALL be renamed to
  `~/.claude/skills/audit.archived-20260427-150000`, the file contents
  SHALL be unchanged, and no file SHALL be deleted

#### Scenario: Refuses to archive project-local symlink target

- **GIVEN** the user invokes `skillpod global archive audit` while
  `~/.claude/skills/audit` happens to resolve into the current project's
  `.skillpod/skills/audit`
- **WHEN** the command runs
- **THEN** it SHALL exit with status `1` and report that project-local
  paths cannot be archived

### Requirement: `skillpod global doctor` flags inconsistencies

The system SHALL provide a `skillpod global doctor` subcommand that
enumerates global skill directories and flags:

1. The same skill name installed under more than one agent.
2. A global skill with the same name as a project-local skill in the
   current project's lockfile.
3. Broken symlinks among global skill directories.

The command SHALL exit `0` when no findings have severity `error`,
`1` otherwise.

#### Scenario: Duplicate name across agents

- **GIVEN** `~/.claude/skills/audit/` and `~/.codex/skills/audit/`
  both exist
- **WHEN** the user runs `skillpod global doctor`
- **THEN** the command SHALL emit a `warning`-severity finding listing
  both paths and exit `0`

#### Scenario: Global / local conflict

- **GIVEN** `~/.claude/skills/audit/` exists and the current project's
  lockfile already lists `audit`
- **WHEN** the user runs `skillpod global doctor`
- **THEN** the command SHALL emit an `error`-severity finding noting
  the conflict and exit `1`

### Requirement: `skillpod adapter list` enumerates the adapter registry

The system SHALL provide a `skillpod adapter list` subcommand that
prints, for the manifest in scope, the active adapter for each declared
agent. Columns are `agent | adapter | mode-supported`. The command
SHALL load and instantiate every adapter so that import errors surface
here as well as in `install`.

#### Scenario: Default registry shown

- **GIVEN** a manifest declaring `agents: [claude, codex, gemini]`
  with no custom adapters
- **WHEN** the user runs `skillpod adapter list`
- **THEN** stdout SHALL show three rows, all with adapter
  `skillpod.installer.adapter_default.IdentityAdapter` and
  `mode-supported = symlink, copy, hardlink`

#### Scenario: Custom adapter listed

- **GIVEN** `agents: [{ name: claude, adapter: skillpod_adapters.claude.RichAdapter }, codex]`
- **WHEN** the user runs `skillpod adapter list`
- **THEN** the `claude` row SHALL show `RichAdapter`, the `codex` row
  SHALL show `IdentityAdapter`, and the command SHALL exit `0` only if
  every adapter imported successfully

### Requirement: `skillpod sync --agent <id>` re-renders one agent

The system SHALL extend `skillpod sync` with an optional `--agent <id>`
flag. When supplied, sync SHALL re-fan-out only the targets under
`.<id>/skills/`, leaving every other agent's fan-out directory
untouched. When omitted, the existing behaviour from the MVP is
preserved (full sync across every agent in the manifest).

#### Scenario: Single-agent re-render

- **GIVEN** a project where `agents: [claude, codex, gemini]` and all
  three are currently materialised
- **WHEN** the user changes `agents.claude.adapter` and runs
  `skillpod sync --agent claude`
- **THEN** every entry under `.claude/skills/` SHALL be deleted and
  re-rendered through the updated adapter, while
  `.codex/skills/` and `.gemini/skills/` SHALL be unchanged

#### Scenario: Unknown agent rejected

- **WHEN** the user runs `skillpod sync --agent foobar` against a
  manifest whose agents list does not include `foobar`
- **THEN** the command SHALL exit `1` with an error citing the
  unrecognised agent, and SHALL NOT touch any agent fan-out directory

