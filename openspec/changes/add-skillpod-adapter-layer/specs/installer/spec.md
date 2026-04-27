# installer spec delta — add-skillpod-adapter-layer

## MODIFIED Requirements

### Requirement: Default install policy

The system SHALL accept the `install.mode` values `symlink` (default),
`copy`, and `hardlink`, and the `install.fallback` list whose default
is `[copy]`. `install.on_missing` retains the MVP default of `error`.

`mode: symlink` materialises every fan-out as a symbolic link.
`mode: copy` materialises every fan-out as an independent recursive
copy. `mode: hardlink` materialises files as hardlinks (sharing the
same inode as the source) and directories as real directories.

#### Scenario: Default install policy unchanged

- **WHEN** the manifest specifies neither `install.mode` nor
  `install.fallback`
- **THEN** the loaded model SHALL set `install.mode` to `symlink` and
  `install.fallback` to `[copy]`

#### Scenario: Unresolvable skill aborts install

- **GIVEN** a manifest skill with no matching source and an unreachable
  registry
- **WHEN** `skillpod install` runs with default policy
- **THEN** the command SHALL fail with a non-zero exit and SHALL NOT
  install any other skill from the same run

#### Scenario: Symlink failure auto-degrades to copy

- **GIVEN** `install.mode: symlink`, `install.fallback: [copy]`, on a
  host where `os.symlink` raises `OSError`
- **WHEN** the installer attempts to fan out a skill
- **THEN** it SHALL retry as `copy`, emit a warning naming the affected
  agent and skill, and the resulting fan-out target SHALL be a real
  directory tree

#### Scenario: Cross-device hardlink degrades to copy

- **GIVEN** `install.mode: hardlink` with the project on one filesystem
  and `~/.cache/skillpod/` on another
- **WHEN** install runs
- **THEN** the installer SHALL detect the device mismatch before any
  hardlink call, materialise via `copy` instead, and emit a single
  warning explaining the downgrade

### Requirement: Symlink fan-out targets per agent

The system SHALL create a fan-out entry at `.<agent>/skills/<name>` for
every agent listed in `agents:` and every installed skill, materialised
according to the active `install.mode` (or chosen fallback). The
supported target directories are `.claude/skills`, `.codex/skills`,
`.gemini/skills`, `.cursor/skills`, `.opencode/skills`, and
`.antigravity/skills`.

#### Scenario: Three-agent fan-out under copy mode

- **GIVEN** `agents: [claude, codex, gemini]`, `install.mode: copy`,
  and a single installed skill `audit`
- **WHEN** install completes
- **THEN** `.claude/skills/audit/`, `.codex/skills/audit/`, and
  `.gemini/skills/audit/` SHALL exist as independent recursive copies
  of `.skillpod/skills/audit/`, none of them SHALL be symlinks, and
  modifying a file in one SHALL NOT affect the others

#### Scenario: Hardlink fan-out preserves inodes

- **GIVEN** `install.mode: hardlink` with project and cache on the same
  filesystem
- **WHEN** a skill containing `manifest.json` is installed
- **THEN** `os.stat(".skillpod/skills/audit/manifest.json").st_ino`
  SHALL equal `os.stat(".claude/skills/audit/manifest.json").st_ino`

## ADDED Requirements

### Requirement: Adapter interface for fan-out

The system SHALL invoke a registered `Adapter` for each `(agent, skill)`
pair during fan-out. The adapter SHALL be passed the canonical
`source_dir = .skillpod/skills/<name>/`, the per-agent
`target_dir = .<agent>/skills/<name>/`, and the active `InstallMode`.
The adapter owns materialisation of `target_dir` for that pair.

A default `IdentityAdapter` SHALL be registered for every supported
agent and SHALL produce the symlink/copy/hardlink behaviour documented
under "Default install policy". This preserves MVP behaviour for any
project that does not configure custom adapters.

#### Scenario: Default adapter matches MVP

- **GIVEN** a manifest that does not configure any custom adapter
- **WHEN** `skillpod install` runs in `mode: symlink`
- **THEN** every agent fan-out target SHALL be a symbolic link
  pointing at `.skillpod/skills/<name>/`, identical to the behaviour
  delivered by `add-skillpod-mvp-install`

### Requirement: Custom adapter resolution and import errors

The system SHALL accept a per-agent adapter override declared as
`agents.<id>.adapter: <dotted.path>` in `skillfile.yml`. At install
time the system SHALL import that path, instantiate the adapter, and
register it in place of `IdentityAdapter` for that agent. An import or
attribute lookup failure SHALL abort the install before any
filesystem mutation occurs.

#### Scenario: Adapter import resolves and is used

- **GIVEN** `agents: [{ name: claude, adapter: skillpod_adapters.claude.RichAdapter }]`
- **WHEN** install runs
- **THEN** the installer SHALL import that module, call
  `RichAdapter().adapt(...)` for every claude/skill pair, and SHALL
  NOT call `IdentityAdapter` for those pairs

#### Scenario: Adapter import fails before fan-out

- **GIVEN** `agents: [{ name: claude, adapter: nonexistent.module:Adapter }]`
- **WHEN** install runs
- **THEN** the command SHALL exit non-zero with an `AdapterImportError`,
  no skill SHALL be materialised, and no fan-out symlink SHALL be
  written

### Requirement: Adapter MUST NOT mutate source_dir

The system SHALL treat `.skillpod/skills/<name>/` as immutable for the
duration of an install run. Adapters SHALL only write inside
`target_dir`; any write to `source_dir` SHALL be considered a contract
violation. The installer SHALL detect and report (post-run) any change
in mtime/size of files inside `source_dir` between adapter invocation
and end of run.

#### Scenario: Misbehaving adapter is reported

- **GIVEN** a custom adapter that erroneously writes a file under
  `source_dir` during `adapt(...)`
- **WHEN** install completes the fan-out for that agent
- **THEN** the installer SHALL emit an `error`-severity diagnostic
  naming the adapter and the modified path, and SHALL exit non-zero
  even if the fan-out itself appeared to succeed
