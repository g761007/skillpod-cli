# registry-discovery spec delta — add-skillpod-trust-and-search

## MODIFIED Requirements

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

## ADDED Requirements

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
