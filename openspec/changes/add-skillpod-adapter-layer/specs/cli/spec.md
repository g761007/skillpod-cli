# cli spec delta — add-skillpod-adapter-layer

## ADDED Requirements

### Requirement: `skillpod adapter list` enumerates the adapter registry

The system SHALL provide a `skillpod adapter list` subcommand that
prints, for the manifest in scope, the active adapter for each declared
agent. Columns are `agent | adapter | mode-supported`. The command
SHALL load and instantiate every adapter so that import errors surface
here as well as in `install`.

#### Scenario: Default registry shown

- **GIVEN** a manifest declaring `agents: [claude, codex, gemini]`
  with no custom adapters
- **WHEN** the user runs `skillpod adapter list`
- **THEN** stdout SHALL show three rows, all with adapter
  `skillpod.installer.adapter_default.IdentityAdapter` and
  `mode-supported = symlink, copy, hardlink`

#### Scenario: Custom adapter listed

- **GIVEN** `agents: [{ name: claude, adapter: skillpod_adapters.claude.RichAdapter }, codex]`
- **WHEN** the user runs `skillpod adapter list`
- **THEN** the `claude` row SHALL show `RichAdapter`, the `codex` row
  SHALL show `IdentityAdapter`, and the command SHALL exit `0` only if
  every adapter imported successfully

### Requirement: `skillpod sync --agent <id>` re-renders one agent

The system SHALL extend `skillpod sync` with an optional `--agent <id>`
flag. When supplied, sync SHALL re-fan-out only the targets under
`.<id>/skills/`, leaving every other agent's fan-out directory
untouched. When omitted, the existing behaviour from the MVP is
preserved (full sync across every agent in the manifest).

#### Scenario: Single-agent re-render

- **GIVEN** a project where `agents: [claude, codex, gemini]` and all
  three are currently materialised
- **WHEN** the user changes `agents.claude.adapter` and runs
  `skillpod sync --agent claude`
- **THEN** every entry under `.claude/skills/` SHALL be deleted and
  re-rendered through the updated adapter, while
  `.codex/skills/` and `.gemini/skills/` SHALL be unchanged

#### Scenario: Unknown agent rejected

- **WHEN** the user runs `skillpod sync --agent foobar` against a
  manifest whose agents list does not include `foobar`
- **THEN** the command SHALL exit `1` with an error citing the
  unrecognised agent, and SHALL NOT touch any agent fan-out directory
