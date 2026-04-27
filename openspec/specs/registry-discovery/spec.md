# registry-discovery Specification

## Purpose
TBD - created by archiving change add-skillpod-mvp-install. Update Purpose after archive.
## Requirements
### Requirement: Skills.sh lookup as discovery fallback

The system SHALL query the skills.sh registry whenever a skill in the
manifest does not match any declared `sources` entry. The query result
SHALL provide enough data to construct a git source: at minimum
`host`, `org`, `repo`, `ref`, and a resolved `commit` SHA.

The result SHALL also include the trust signals `verified` (bool),
`installs` (int), and `stars` (int), surfaced from the registry
response. These values SHALL be available to both the install pipeline
and the `search` subcommand.

#### Scenario: Unknown skill resolved through registry

- **GIVEN** a manifest with `skills: [polish]` and no source covering
  `polish`
- **WHEN** the user runs `skillpod install`
- **THEN** the system SHALL issue a single GET to skills.sh for `polish`,
  receive a GitHub repo + ref + the trust signals, and hand off
  resolution to source-resolver as a synthetic `git` source

### Requirement: Registry data never reaches the lockfile

The system SHALL strip registry identity from the resolution result
before writing the lockfile. The lockfile entry SHALL reference only the
underlying git source.

#### Scenario: Registry name absent from lockfile entry

- **WHEN** a registry-resolved skill is locked
- **THEN** the resulting `skillfile.lock` entry SHALL contain only
  `source: git`, `url`, `commit`, and `sha256`, and SHALL omit any
  registry identifier

### Requirement: Registry failure is fatal, not silent

The system SHALL fail the operation when the registry is unreachable,
returns a non-2xx response, returns malformed data, or omits required
fields. The system SHALL NOT fall back to mirrors, caches, or partial
data.

#### Scenario: Registry timeout aborts install

- **GIVEN** the skills.sh endpoint is unreachable (timeout, DNS failure,
  or 5xx)
- **WHEN** `skillpod install` would otherwise need to query it
- **THEN** the command SHALL exit with a non-zero status, surface the
  underlying error to the user, and SHALL NOT modify `.skillpod/` or any
  agent fan-out directory

### Requirement: Registry is never written

The system SHALL treat skills.sh as read-only. No subcommand introduced
in this change SHALL publish, mutate, or POST to the registry.

#### Scenario: No registry write in MVP CLI

- **WHEN** any subcommand from this change (`init`, `install`, `add`,
  `remove`, `list`, `sync`) executes
- **THEN** the only registry traffic permitted SHALL be HTTP `GET`
  requests issued by the discovery client

### Requirement: Trust policy enforcement on registry results

The system SHALL evaluate every registry result against the active
`registry.skills_sh` trust policy before allowing it to flow into the
install pipeline or be presented as installable in `search` output. A
result SHALL fail enforcement when:

- `verified` is `false` and `allow_unverified` is `false`, OR
- `installs` is below `min_installs`, OR
- `stars` is below `min_stars`.

A failed result SHALL produce a typed `TrustError` listing every
threshold that was violated; install / add / update SHALL abort, and
search SHALL still display the row but mark it as policy-failing.

#### Scenario: Verified skill passes default policy

- **GIVEN** a manifest using default trust policy
  (`allow_unverified: false`, `min_installs: 0`, `min_stars: 0`)
- **AND** a registry result with `verified: true`, `installs: 5`,
  `stars: 1`
- **WHEN** `skillpod install` resolves the skill
- **THEN** the result SHALL pass enforcement and resolution SHALL
  continue normally

#### Scenario: Unverified skill blocked by default

- **GIVEN** the default trust policy
- **AND** a registry result with `verified: false`
- **WHEN** `skillpod install` would otherwise resolve it
- **THEN** the system SHALL raise `TrustError` listing
  `verified=false` as the reason, abort the install, and exit
  non-zero

#### Scenario: Multiple thresholds reported together

- **GIVEN** policy
  `{ allow_unverified: false, min_installs: 1000, min_stars: 50 }`
- **AND** a result with `verified: false, installs: 12, stars: 3`
- **WHEN** the trust filter runs
- **THEN** the resulting `TrustError` SHALL list all three failed
  thresholds in a single error so the user fixes them at once

