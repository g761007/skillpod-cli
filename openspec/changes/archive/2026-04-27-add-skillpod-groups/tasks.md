# Tasks — add-skillpod-groups

## 1. Manifest extension
- [x] 1.1 Add `groups: dict[str, list[SkillRef]] = {}` and `use: list[str] = []` to `Skillfile`. `SkillRef` is the same shorthand-or-object type used in `skills`.
- [x] 1.2 Validation: every `use[]` name must exist in `groups`; group entries follow the same rules as `skills[]`; group/skill names must not collide.
- [x] 1.3 Tests: minimal manifest with one group; nested duplicates dedup correctly; invalid `use:` reference is rejected.

## 2. user_skills contract
- [x] 2.1 Document and implement: any directory under `.skillpod/user_skills/<name>/` is a skill named `<name>`.
- [x] 2.2 Manifest validator: emit a warning if a `user_skills` entry shares its name with a manifest skill (priority will silently shadow).
- [x] 2.3 Tests: a project with only `user_skills/audit/` and an empty manifest still installs `audit`.

## 3. Installer flattening + priority
- [x] 3.1 Implement `installer/expand.py:flatten(manifest)` returning the union of `skills[]` plus every `groups[g]` for `g in use[]`, deduplicated by name (last writer with explicit `source` wins).
- [x] 3.2 Update resolver entry points to apply
  `user_skills > sources (priority desc) > registry` order.
- [x] 3.3 Lockfile writer now operates on the flattened set; group/use are not persisted.
- [x] 3.4 Tests: `use: [frontend]` expands correctly; user_skills shadow same-name registry skills; lockfile after a group install matches lockfile of an equivalent flat manifest.

## 4. `skillpod global …` advisory CLI
- [x] 4.1 `cli/commands/global_list.py` — print every directory found under known global agent paths (`~/.claude/skills/`, `~/.codex/skills/`, …) with size + last-modified.
- [x] 4.2 `cli/commands/global_archive.py <skill>` — rename `<dir>` to `<dir>.archived-YYYYMMDD-HHMMSS` (no deletion). Refuse to operate on a path inside the project working tree.
- [x] 4.3 `cli/commands/global_doctor.py` — flag duplicate skill names across agents; flag globals also installed locally (potential conflict).
- [x] 4.4 Tests: list against a fake `$HOME`; archive renames and is reversible by hand; doctor flags duplicates.

## 5. Validation gate
- [x] 5.1 `openspec validate add-skillpod-groups --strict` passes.
- [x] 5.2 `pytest -q` passes.
- [x] 5.3 Manual: in a scratch repo, create `groups: { frontend: [audit, polish] }` + `use: [frontend]`, run install, confirm both skills installed and lockfile flattens them.
