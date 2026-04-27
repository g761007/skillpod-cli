# manifest spec delta — add-skillpod-mvp-install

## ADDED Requirements

### Requirement: Manifest parsing and defaults

The system SHALL parse `skillfile.yml` into a typed model containing the
fields `version`, `registry`, `agents`, `install`, `sources`, and `skills`,
applying deterministic defaults for any omitted top-level field.

#### Scenario: Minimal manifest with only `skills`

- **WHEN** the user authors a `skillfile.yml` containing only
  `version: 1` and `skills: [audit]`
- **THEN** the loaded model SHALL set `registry.default` to `"skills.sh"`,
  `agents` to `[]`, `install.mode` to `"symlink"`, `install.on_missing`
  to `"error"`, and `sources` to `[]`

#### Scenario: Unknown top-level key rejected

- **WHEN** the manifest contains a top-level key not defined by the schema
  (e.g. `groups:` in 0.1.0)
- **THEN** loading SHALL fail with a validation error citing the offending
  key, and SHALL NOT silently drop it

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
