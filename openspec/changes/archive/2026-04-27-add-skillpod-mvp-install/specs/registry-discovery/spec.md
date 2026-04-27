# registry-discovery spec delta — add-skillpod-mvp-install

## ADDED Requirements

### Requirement: Skills.sh lookup as discovery fallback

The system SHALL query the skills.sh registry whenever a skill in the
manifest does not match any declared `sources` entry. The query result
SHALL provide enough data to construct a git source: at minimum
`host`, `org`, `repo`, `ref`, and a resolved `commit` SHA.

#### Scenario: Unknown skill resolved through registry

- **GIVEN** a manifest with `skills: [polish]` and no source covering
  `polish`
- **WHEN** the user runs `skillpod install`
- **THEN** the system SHALL issue a single GET to skills.sh for `polish`,
  receive a GitHub repo + ref, and hand off resolution to
  source-resolver as a synthetic `git` source

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
