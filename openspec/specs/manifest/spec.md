# manifest Specification

## Purpose
TBD - created by archiving change add-skillpod-mvp-install. Update Purpose after archive.
## Requirements
### Requirement: Manifest parsing and defaults

The system SHALL parse `skillfile.yml` into a typed model containing the
fields `version`, `registry`, `agents`, `install`, `sources`, and
`skills`, applying deterministic defaults for any omitted top-level
field.

The `registry.skills_sh` block SHALL accept the additional fields
`allow_unverified` (bool, default `false`), `min_installs` (int, default
`0`), and `min_stars` (int, default `0`). Defaults SHALL preserve the
behaviour of `add-skillpod-mvp-install` so manifests authored before
this change continue to load without modification.

#### Scenario: Minimal manifest with only `skills`

- **WHEN** the user authors a `skillfile.yml` containing only
  `version: 1` and `skills: [audit]`
- **THEN** the loaded model SHALL set `registry.default` to `"skills.sh"`,
  `agents` to `[]`, `install.mode` to `"symlink"`, `install.on_missing`
  to `"error"`, `sources` to `[]`, and SHALL set
  `registry.skills_sh.allow_unverified` to `false`,
  `registry.skills_sh.min_installs` to `0`, and
  `registry.skills_sh.min_stars` to `0`

#### Scenario: Unknown top-level key rejected

- **WHEN** the manifest contains a top-level key not defined by the
  schema (e.g. `groups:` in 0.2.0)
- **THEN** loading SHALL fail with a validation error citing the
  offending key, and SHALL NOT silently drop it

#### Scenario: Trust policy fields round-trip

- **GIVEN** a manifest with
  `registry.skills_sh: { allow_unverified: true, min_installs: 1000, min_stars: 50 }`
- **WHEN** the manifest is loaded and re-serialised
- **THEN** all three fields SHALL retain their declared values, and the
  loader SHALL reject non-integer values for `min_installs` /
  `min_stars` and non-boolean values for `allow_unverified`

### Requirement: Skill entry shorthand and full forms

The system SHALL accept skill entries either as bare strings (shorthand) or
as objects with at least a `name` field, plus optional `source` and
`version`. Both forms SHALL produce equivalent in-memory `SkillEntry`
records.

#### Scenario: Shorthand string entry

- **WHEN** the manifest contains `skills: [audit]`
- **THEN** the loaded model SHALL contain a single `SkillEntry` whose
  `name` is `"audit"` and whose `source` and `version` are `None`

#### Scenario: Object entry with explicit source

- **WHEN** the manifest contains
  `skills: [{ name: custom-skill, source: anthropic }]`
- **THEN** the loaded model SHALL contain a `SkillEntry` whose `source`
  equals the matching `sources[].name`; if no such source exists,
  validation SHALL fail with a clear error

### Requirement: Agents allow-list controls fan-out

The system SHALL only consider the agents declared under the top-level
`agents:` list as targets for symlink fan-out. Agents not listed SHALL
NOT receive directories or symlinks during install.

#### Scenario: Restricting fan-out to two agents

- **WHEN** `agents: [claude, codex]` is declared and a skill is installed
- **THEN** symlinks SHALL appear under `.claude/skills/` and
  `.codex/skills/`, and SHALL NOT appear under `.gemini/skills/`,
  `.cursor/skills/`, `.opencode/skills/`, or `.antigravity/skills/`

### Requirement: Recognised agents

The system SHALL recognise the agent identifiers `claude`, `codex`,
`gemini`, `cursor`, `opencode`, and `antigravity` and map each to a
fan-out target directory of the form `.<agent>/skills/`.

#### Scenario: Unknown agent rejected

- **WHEN** the user declares `agents: [foobar]`
- **THEN** manifest validation SHALL fail listing the supported agent
  identifiers

### Requirement: Named groups and `use` selectors

The system SHALL accept a top-level `groups:` mapping where each key is
a group name and each value is a list of skill entries (shorthand string
or object), and a top-level `use:` list of group names. At install time
every group named in `use` SHALL contribute its members to the effective
skill set, deduplicated by name.

#### Scenario: Single group expanded via use

- **GIVEN** a manifest with
  `groups: { frontend: [audit, web-design] }` and `use: [frontend]`
- **WHEN** the manifest is loaded
- **THEN** the effective skill set SHALL contain `audit` and
  `web-design` even though `skills:` is empty

#### Scenario: Group reference must exist

- **WHEN** the manifest contains `use: [backend]` but no `groups.backend`
- **THEN** loading SHALL fail with a validation error naming the missing
  group, and the install pipeline SHALL NOT run

#### Scenario: Group and skill names cannot collide

- **WHEN** the manifest defines `groups: { audit: [...] }` and also
  declares `skills: [audit]`
- **THEN** loading SHALL fail because the name `audit` is ambiguous

### Requirement: `.skillpod/user_skills/` contract

The system SHALL treat every directory immediately under
`.skillpod/user_skills/` as a skill whose name is the directory's own
name. User skills SHALL participate in install fan-out alongside skills
declared in the manifest, and SHALL take priority over both `sources`
and the registry when names collide.

#### Scenario: Bare user skill installed without a manifest entry

- **GIVEN** an otherwise empty manifest and a directory
  `.skillpod/user_skills/audit/`
- **WHEN** the user runs `skillpod install`
- **THEN** the install pipeline SHALL include `audit`, materialise it
  via the user_skills directory, and fan out symlinks for every declared
  agent

#### Scenario: User skill shadows a registry skill of the same name

- **GIVEN** a manifest declaring `skills: [audit]` resolving against
  the registry
- **AND** a directory `.skillpod/user_skills/audit/`
- **WHEN** install runs
- **THEN** the materialised `audit` SHALL come from the user_skills
  directory, the registry SHALL NOT be queried for `audit`, and the
  loader SHALL emit a warning that the user skill is shadowing the
  manifest entry

