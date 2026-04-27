# lockfile spec delta — add-skillpod-mvp-install

## ADDED Requirements

### Requirement: Lockfile records git-pinned skills

The system SHALL produce `skillfile.lock` after every successful install
or `add` operation, recording each git-resolved skill with the fields
`source`, `url`, `commit` (full 40-character SHA), and `sha256`
(content digest of the materialised skill directory).

#### Scenario: Lockfile after first install

- **WHEN** `skillpod install` completes successfully against a manifest
  whose only skill resolves to commit `abc123…` of
  `https://github.com/vercel-labs/agent-skills`
- **THEN** `skillfile.lock` SHALL contain `resolved.<name>` with
  `source: git`, the matching `url`, the full `commit`, and a
  non-empty `sha256`

### Requirement: Registry name is excluded from the lockfile

The system SHALL NOT write the registry name (e.g. `skills.sh`) into the
lockfile. Only the resolved git source data SHALL be recorded, so the
lockfile remains valid even if the registry disappears.

#### Scenario: Registry-resolved skill locks to git only

- **WHEN** a skill `audit` is added without an explicit source and is
  resolved through the registry to a GitHub repo
- **THEN** the resulting lockfile entry SHALL contain only `source`,
  `url`, `commit`, and `sha256`, and SHALL NOT contain a `registry` field

### Requirement: Local sources are not locked

The system SHALL NOT record skills resolved from `local` sources in the
lockfile, because local paths are not reproducible across machines. Such
skills SHALL be re-resolved from the manifest on every install.

#### Scenario: Manifest with a local skill produces no lock entry

- **GIVEN** a manifest declaring a skill backed by a `local` source
- **WHEN** `skillpod install` runs successfully
- **THEN** `skillfile.lock` SHALL NOT contain that skill under
  `resolved`

### Requirement: Frozen install enforcement

The system SHALL run `skillpod install` in frozen mode whenever
`skillfile.lock` exists. Any divergence between resolved commit/sha256
and the lockfile entry SHALL abort the install with a non-zero exit
code, leaving the project unchanged.

#### Scenario: Lockfile commit drift aborts install

- **GIVEN** `skillfile.lock` records commit `abc123…` for skill `audit`
- **AND** the registry now reports the latest commit as `def456…`
- **WHEN** the user runs `skillpod install`
- **THEN** the command SHALL fail with a non-zero exit code, report the
  divergence, and SHALL NOT modify `.skillpod/` or any agent fan-out
  directories
