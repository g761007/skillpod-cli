# cli spec delta — add-skillpod-trust-and-search

## ADDED Requirements

### Requirement: `skillpod search` discovers registry skills

The system SHALL provide a `skillpod search <query>` subcommand that
queries the registry for skills matching `<query>`, renders the matches
in a stable column order (`name`, `repo`, `installs`, `stars`,
`verified`, `passes-policy`), and supports `--limit <n>` (default `20`)
and `--json` for machine-readable output.

#### Scenario: Search shows policy-pass badge

- **GIVEN** the active manifest enforces
  `min_installs: 1000, min_stars: 50, allow_unverified: false`
- **AND** the registry returns three results: A (verified, 5000
  installs, 200 stars), B (verified, 12 installs, 1 star), C
  (unverified, 1 install, 0 stars)
- **WHEN** the user runs `skillpod search audit`
- **THEN** all three rows SHALL appear, with `passes-policy` `true` for
  A and `false` for B and C; the command SHALL exit `0`

#### Scenario: Search JSON output

- **WHEN** the user runs `skillpod search audit --json`
- **THEN** stdout SHALL be a single JSON document of the form
  `{ "query": "audit", "results": [ { "name": ..., "repo": ...,
  "installs": ..., "stars": ..., "verified": ..., "passes_policy": ... }, ... ] }`

### Requirement: `skillpod outdated` reports lockfile drift

The system SHALL provide a `skillpod outdated` subcommand that, for each
entry in `skillfile.lock`, fetches the current latest commit
(through the registry for registry-resolved skills, or via
`git ls-remote` for explicit git sources) and reports per-skill drift.

#### Scenario: One skill drifted

- **GIVEN** `skillfile.lock` has `audit -> commit abc123…` and the
  upstream now points at `def456…`
- **WHEN** the user runs `skillpod outdated`
- **THEN** stdout SHALL report a row showing `audit | abc123 | def456`
  and the command SHALL exit `0`

#### Scenario: Outdated handles network failure

- **GIVEN** the registry is unreachable
- **WHEN** the user runs `skillpod outdated`
- **THEN** the command SHALL exit `2` and surface the underlying error,
  without partially printing rows

### Requirement: `skillpod update` refreshes the lockfile

The system SHALL provide a `skillpod update [skill]` subcommand that
re-runs the install pipeline in a "force re-resolve" mode. When invoked
with a name, only that skill SHALL be updated; without arguments, every
manifest skill SHALL be refreshed. Trust policy SHALL still be enforced
on the new resolution result.

#### Scenario: Update single skill

- **WHEN** the user runs `skillpod update audit`
- **THEN** the command SHALL re-resolve only `audit`, refresh its
  lockfile entry, leave other lockfile entries untouched, and exit `0`

#### Scenario: Update aborts on trust failure

- **GIVEN** a previously trusted `audit` was downgraded by the registry
  to `verified: false`
- **AND** the policy still requires `allow_unverified: false`
- **WHEN** `skillpod update audit` runs
- **THEN** the command SHALL raise `TrustError`, exit `1`, and SHALL
  NOT modify `skillfile.lock` or `.skillpod/skills/audit`

### Requirement: `skillpod doctor` verifies project consistency

The system SHALL provide a `skillpod doctor` subcommand that performs
each of the following checks and reports findings with severity
`error` or `warning`:

1. Every manifest skill exists in `skillfile.lock` (or is local-sourced).
2. Every lockfile entry has a materialised directory at
   `.skillpod/skills/<name>/`.
3. Every `.<agent>/skills/<name>` symlink declared by the manifest
   resolves into `.skillpod/skills/`.
4. No directory exists under `.skillpod/skills/` that is not referenced
   by the manifest.

The command SHALL exit `0` when no findings have severity `error`,
`1` otherwise, and `2` if the filesystem cannot be read.

#### Scenario: Clean project

- **GIVEN** a project that has just successfully run `skillpod install`
- **WHEN** the user runs `skillpod doctor`
- **THEN** the command SHALL print a "no findings" summary and exit
  `0`

#### Scenario: Broken symlink detected

- **GIVEN** a project where `.claude/skills/audit` points at a path that
  no longer exists
- **WHEN** the user runs `skillpod doctor`
- **THEN** the command SHALL emit an `error`-severity finding referring
  to that symlink and exit `1`

#### Scenario: Orphan directory under .skillpod/skills

- **GIVEN** `.skillpod/skills/legacy/` exists but `legacy` is not in
  the manifest
- **WHEN** the user runs `skillpod doctor`
- **THEN** the command SHALL emit a `warning`-severity finding listing
  the orphan directory; without other errors, it SHALL still exit `0`
