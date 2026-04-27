# cli spec delta — add-skillpod-groups

## ADDED Requirements

### Requirement: `skillpod global list` enumerates global skills

The system SHALL provide a `skillpod global list` subcommand that scans
known global agent skill directories under `$HOME` (`~/.claude/skills/`,
`~/.codex/skills/`, `~/.gemini/skills/`, `~/.cursor/skills/`,
`~/.opencode/skills/`, `~/.antigravity/skills/`) and prints each
discovered skill with its agent, size, and last-modified time. The
command SHALL NOT modify any of those directories.

#### Scenario: Lists skills across two agents

- **GIVEN** `~/.claude/skills/audit/` and `~/.codex/skills/polish/`
  exist
- **WHEN** the user runs `skillpod global list`
- **THEN** the command SHALL emit a row for `audit` (claude) and a row
  for `polish` (codex), and SHALL NOT touch either directory

#### Scenario: JSON output

- **WHEN** the user runs `skillpod global list --json`
- **THEN** stdout SHALL be a JSON array of objects with stable keys
  `agent`, `name`, `path`, `size_bytes`, `mtime`

### Requirement: `skillpod global archive` is non-destructive

The system SHALL provide a `skillpod global archive <skill>` subcommand
that renames every matching global skill directory to
`<original>.archived-YYYYMMDD-HHMMSS` (UTC). The command SHALL NEVER
delete files, and SHALL refuse to act on any path that resolves inside
the current project working tree.

#### Scenario: Archive renames the global skill

- **GIVEN** `~/.claude/skills/audit/` exists
- **WHEN** the user runs `skillpod global archive audit` at
  `2026-04-27T15:00:00Z`
- **THEN** the directory SHALL be renamed to
  `~/.claude/skills/audit.archived-20260427-150000`, the file contents
  SHALL be unchanged, and no file SHALL be deleted

#### Scenario: Refuses to archive project-local symlink target

- **GIVEN** the user invokes `skillpod global archive audit` while
  `~/.claude/skills/audit` happens to resolve into the current project's
  `.skillpod/skills/audit`
- **WHEN** the command runs
- **THEN** it SHALL exit with status `1` and report that project-local
  paths cannot be archived

### Requirement: `skillpod global doctor` flags inconsistencies

The system SHALL provide a `skillpod global doctor` subcommand that
enumerates global skill directories and flags:

1. The same skill name installed under more than one agent.
2. A global skill with the same name as a project-local skill in the
   current project's lockfile.
3. Broken symlinks among global skill directories.

The command SHALL exit `0` when no findings have severity `error`,
`1` otherwise.

#### Scenario: Duplicate name across agents

- **GIVEN** `~/.claude/skills/audit/` and `~/.codex/skills/audit/`
  both exist
- **WHEN** the user runs `skillpod global doctor`
- **THEN** the command SHALL emit a `warning`-severity finding listing
  both paths and exit `0`

#### Scenario: Global / local conflict

- **GIVEN** `~/.claude/skills/audit/` exists and the current project's
  lockfile already lists `audit`
- **WHEN** the user runs `skillpod global doctor`
- **THEN** the command SHALL emit an `error`-severity finding noting
  the conflict and exit `1`
