# manifest spec delta — add-skillpod-trust-and-search

## MODIFIED Requirements

### Requirement: Manifest parsing and defaults

The system SHALL parse `skillfile.yml` into a typed model containing the
fields `version`, `registry`, `agents`, `install`, `sources`, and
`skills`, applying deterministic defaults for any omitted top-level
field.

The `registry.skills_sh` block SHALL accept the additional fields
`allow_unverified` (bool, default `false`), `min_installs` (int, default
`0`), and `min_stars` (int, default `0`). Defaults SHALL preserve the
behaviour of `add-skillpod-mvp-install` so manifests authored before
this change continue to load without modification.

#### Scenario: Minimal manifest with only `skills`

- **WHEN** the user authors a `skillfile.yml` containing only
  `version: 1` and `skills: [audit]`
- **THEN** the loaded model SHALL set `registry.default` to `"skills.sh"`,
  `agents` to `[]`, `install.mode` to `"symlink"`, `install.on_missing`
  to `"error"`, `sources` to `[]`, and SHALL set
  `registry.skills_sh.allow_unverified` to `false`,
  `registry.skills_sh.min_installs` to `0`, and
  `registry.skills_sh.min_stars` to `0`

#### Scenario: Unknown top-level key rejected

- **WHEN** the manifest contains a top-level key not defined by the
  schema (e.g. `groups:` in 0.2.0)
- **THEN** loading SHALL fail with a validation error citing the
  offending key, and SHALL NOT silently drop it

#### Scenario: Trust policy fields round-trip

- **GIVEN** a manifest with
  `registry.skills_sh: { allow_unverified: true, min_installs: 1000, min_stars: 50 }`
- **WHEN** the manifest is loaded and re-serialised
- **THEN** all three fields SHALL retain their declared values, and the
  loader SHALL reject non-integer values for `min_installs` /
  `min_stars` and non-boolean values for `allow_unverified`
