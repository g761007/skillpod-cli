# installer spec delta — add-skillpod-mvp-install

## ADDED Requirements

### Requirement: Install pipeline ordering

The system SHALL execute installs in this order:
`read manifest -> resolve sources -> fetch into cache -> materialise
.skillpod/skills/<name> -> fan out symlinks to enabled agents -> write
skillfile.lock`. A failure in any step SHALL abort the operation and
leave the project filesystem unchanged from before the run.

#### Scenario: Failure during fan-out rolls back

- **GIVEN** install has materialised two skills under `.skillpod/skills/`
- **WHEN** symlink creation for the third skill fails (e.g. target name
  collides with an unmanaged file)
- **THEN** the system SHALL not write `skillfile.lock`, SHALL remove any
  partially created `.skillpod/skills/<name>` and agent symlinks for the
  current run, and SHALL exit with a non-zero status

### Requirement: Default install policy

The system SHALL default `install.mode` to `symlink` and `on_missing` to
`error`. Symlink mode means each skill is exposed via a symbolic link;
`on_missing: error` means a manifest skill that cannot be resolved is a
hard failure rather than a skip.

#### Scenario: Unresolvable skill aborts install

- **GIVEN** a manifest skill with no matching source and an unreachable
  registry
- **WHEN** `skillpod install` runs with default policy
- **THEN** the command SHALL fail with a non-zero exit and SHALL NOT
  install any other skill from the same run

### Requirement: Materialisation under .skillpod/skills

The system SHALL place each installed skill at
`.skillpod/skills/<name>/`, regardless of agent fan-out. This directory
SHALL be the single source of truth for the installed contents and SHALL
be the link target referenced by every agent fan-out symlink.

#### Scenario: Project install root is sole materialisation point

- **WHEN** `skillpod install` succeeds for skill `audit`
- **THEN** `.skillpod/skills/audit/` SHALL exist (symlink or directory),
  and every agent fan-out entry for `audit` SHALL ultimately resolve to
  it

### Requirement: Symlink fan-out targets per agent

The system SHALL create a symlink at `.<agent>/skills/<name>` for every
agent listed in `agents:` and every installed skill. The supported
target directories are `.claude/skills`, `.codex/skills`,
`.gemini/skills`, `.cursor/skills`, `.opencode/skills`, and
`.antigravity/skills`.

#### Scenario: Three-agent fan-out

- **GIVEN** `agents: [claude, codex, gemini]` and a single installed
  skill `audit`
- **WHEN** install completes
- **THEN** `.claude/skills/audit`, `.codex/skills/audit`, and
  `.gemini/skills/audit` SHALL exist as symlinks, each resolving (via
  `.skillpod/skills/audit`) to the same underlying directory

### Requirement: Refusal to overwrite unmanaged paths

The system SHALL refuse to create or replace an agent fan-out symlink
when the target already exists and is not a skillpod-managed symlink
(i.e. its target does not point inside `.skillpod/`).

#### Scenario: Hand-managed skill is preserved

- **GIVEN** `.claude/skills/audit/` already exists as a regular directory
  unrelated to `.skillpod/`
- **WHEN** `skillpod install` would create a symlink at the same path
- **THEN** the command SHALL abort with a non-zero exit, name the
  conflicting path, and SHALL NOT delete or move the existing directory
