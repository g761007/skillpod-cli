# source-resolver spec delta — add-skillpod-mvp-install

## ADDED Requirements

### Requirement: Local source resolution

The system SHALL resolve sources of `type: local` by treating the
configured `path` (after `~` expansion) as the in-place skill root. The
resolver SHALL fail with a clear error when the path does not exist or is
not a directory.

#### Scenario: Local source hit

- **GIVEN** `sources` includes
  `{ name: local, type: local, path: ~/.agents/skills }`
- **AND** a folder `~/.agents/skills/audit/` exists
- **WHEN** the resolver is asked for the `audit` skill
- **THEN** it SHALL return the absolute path to `~/.agents/skills/audit/`
  without copying or moving the directory

### Requirement: Git source resolution and cache layout

The system SHALL resolve sources of `type: git` by cloning the repository
into the global cache and checking out the requested ref. The cache path
SHALL be `~/.cache/skillpod/<host>/<org>/<repo>@<commit>/`, where
`<commit>` is the full 40-character SHA derived via `git rev-parse HEAD`
after checkout.

#### Scenario: Git resolve populates cache

- **GIVEN** an empty `~/.cache/skillpod/`
- **AND** a `git` source pointing at `https://github.com/example/skills`
  with `ref: main`
- **WHEN** the resolver fetches the `audit` skill
- **THEN** a directory matching
  `~/.cache/skillpod/github.com/example/skills@<40-char-sha>/` SHALL
  exist, and its working tree SHALL match the resolved commit

### Requirement: Cache contents are immutable

The system SHALL treat any populated cache directory as immutable: it
SHALL NOT modify, prune, or re-checkout an existing
`<host>/<org>/<repo>@<commit>/` directory. Re-fetching the same commit
SHALL be a no-op.

#### Scenario: Re-running install reuses cache

- **GIVEN** a populated cache for commit `abc123…`
- **WHEN** `skillpod install` is run a second time without manifest
  changes
- **THEN** the resolver SHALL detect the cached commit and SHALL NOT
  perform a new git clone or checkout

### Requirement: Source priority ordering

The system SHALL probe declared sources in descending `priority` order.
A skill SHALL be resolved from the first source whose lookup succeeds,
even if a lower-priority source could also satisfy it.

#### Scenario: Higher priority wins

- **GIVEN** two sources both able to provide skill `audit`:
  `{ name: local, priority: 100 }` and `{ name: anthropic, priority: 80 }`
- **WHEN** the resolver runs
- **THEN** the returned skill path SHALL come from `local`, and the git
  source SHALL NOT be cloned

### Requirement: Explicit skill source overrides probing

The system SHALL bypass priority-ordered probing whenever a `SkillEntry`
declares an explicit `source:` and SHALL resolve only against that
source.

#### Scenario: Explicit source forces git resolution

- **GIVEN** a manifest entry
  `{ name: custom-skill, source: anthropic }` and a higher-priority
  `local` source that also exposes `custom-skill`
- **WHEN** the resolver runs
- **THEN** it SHALL resolve via the `anthropic` git source and SHALL NOT
  return the local copy
