# manifest spec delta — add-skillpod-groups

## ADDED Requirements

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
