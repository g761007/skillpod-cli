# installer spec delta — add-skillpod-groups

## MODIFIED Requirements

### Requirement: Install pipeline ordering

The system SHALL execute installs in this order:
`read manifest -> expand groups -> apply user_skills -> resolve sources
-> fetch into cache -> materialise .skillpod/skills/<name> -> fan out
symlinks to enabled agents -> write skillfile.lock`. A failure in any
step SHALL abort the operation and leave the project filesystem
unchanged from before the run.

The expansion step SHALL produce a flat, deduplicated skill set from
`skills[]` plus every group named in `use[]`. The user_skills step
SHALL substitute any flat-set entry with a same-named user skill before
sources or the registry are consulted.

#### Scenario: Failure during fan-out rolls back

- **GIVEN** install has materialised two skills under
  `.skillpod/skills/`
- **WHEN** symlink creation for the third skill fails (e.g. target name
  collides with an unmanaged file)
- **THEN** the system SHALL not write `skillfile.lock`, SHALL remove
  any partially created `.skillpod/skills/<name>` and agent symlinks
  for the current run, and SHALL exit with a non-zero status

#### Scenario: Group expansion before resolution

- **GIVEN** `groups: { frontend: [audit, polish] }`, `use: [frontend]`,
  `skills: [polish]`
- **WHEN** install runs
- **THEN** the resolver SHALL be invoked once each for `audit` and
  `polish`, and the lockfile SHALL contain exactly those two entries
  (deduplication handled before resolution)

#### Scenario: User skill substitution before source probing

- **GIVEN** a manifest entry `audit` resolvable through both a `local`
  source and the registry, plus `.skillpod/user_skills/audit/`
- **WHEN** install runs
- **THEN** the materialised path SHALL come from
  `.skillpod/user_skills/audit/`; the local source SHALL NOT be probed
  and the registry SHALL NOT be queried

## ADDED Requirements

### Requirement: Effective resolution priority

The system SHALL apply the documented resolution priority on every
install or update:
1. `.skillpod/user_skills/<name>/`
2. Manifest `sources[]` ordered by descending `priority`
3. The registry (skills.sh)

The first matching tier SHALL provide the materialisation; lower tiers
SHALL NOT be consulted for that skill in the same run.

#### Scenario: Priority short-circuits on user skill

- **GIVEN** a skill `audit` is satisfied by a user skill, two sources,
  and the registry
- **WHEN** install runs
- **THEN** only the user skill SHALL be materialised, and the system
  SHALL NOT issue any HTTP request to the registry for that skill
