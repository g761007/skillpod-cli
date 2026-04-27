# Add groups, user_skills, and global advisory CLI (Roadmap 0.3.0)

## Why

The MVP only lets users enumerate skills one-by-one. In real projects skills
cluster by intent: a *frontend* squad wants `audit + web-design + a11y`; a
*backend* squad wants `audit + db-review + sql-lint`. Forcing every project
to repeat that bag of names invites drift.

`plans/skillpod-plan.md` §3 introduces `groups:` and `use:` to express
those clusters declaratively, and §9 introduces `.skillpod/user_skills/` so
that local, in-development skills can sit inside the project without
needing a `local` source declaration. §8 also calls for a thin `global`
advisory CLI: skillpod intentionally never *manages* global skills, but it
should help users see and archive them.

## What Changes

- **manifest** — Add `groups: { name: [skills...] }` and a top-level
  `use: [groupName...]` selector. Add a documented `.skillpod/user_skills/`
  contract: any directory placed there is treated as a skill of the same
  name, with priority above declared sources and registry.
- **installer** — Expand `use:` into the flat skill set before resolution.
  Apply the documented priority order
  `user_skills > sources (by priority) > registry`. The lockfile records
  the *flattened* set, not the group definitions, so projects can add or
  rename groups without churn in `skillfile.lock`.
- **cli** — Add the advisory subcommands `skillpod global list`,
  `skillpod global archive <skill>`, and `skillpod global doctor`. None of
  them mutate global directories beyond writing a sibling
  `<skill>.archived` marker; they exist to give users visibility, not to
  install or delete.

## Impact

- Manifests can collapse repeated lists into named groups.
- `.skillpod/user_skills/` becomes a recognised directory; the installer
  must skip it during the orphan-directory check that `doctor` does.
- New `skillpod global …` subcommands; no impact on other agents.
- Specs touched: `manifest`, `installer`, `cli` (all MODIFIED; no new
  capabilities).

## Non-goals

- A package-manager-style `extends:` for inheriting groups across projects.
- Mutating global skill directories. `archive` only renames in place; we
  never delete user-installed global skills automatically.
- Per-agent group filtering (e.g. "frontend group only for claude") —
  arrives, if needed, with the adapter layer in 0.4.0.
