# cli spec delta — add-skillpod-mvp-install

## ADDED Requirements

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
