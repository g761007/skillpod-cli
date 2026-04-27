# Add trust policy and search/diagnostics commands (Roadmap 0.2.0)

## Why

`plans/skillpod-plan.md` §4.5 calls out the security gap: the upstream
skills.sh registry openly states that it cannot guarantee the quality or
safety of every skill it indexes. The MVP change
(`add-skillpod-mvp-install`) deliberately ignores this — it accepts any
skill the registry returns. That is acceptable for a private bring-up, but
unacceptable for a manager that we want users to depend on by default.

This change introduces:

1. A **trust policy** under `registry.skills.sh.*` so projects can require a
   minimum bar before a skill is allowed (`allow_unverified`,
   `min_installs`, `min_stars`).
2. The **`search` / `outdated` / `update` / `doctor`** subcommands, which
   the plan §10 lists as core CLI surface and which are gated by the new
   trust filter (search must report each result against the active policy
   so users do not accidentally `add` an unsafe skill).

## What Changes

- **manifest** — Add `registry.skills.sh.allow_unverified`,
  `registry.skills.sh.min_installs`, `registry.skills.sh.min_stars`. Defaults
  preserve the MVP behaviour (`allow_unverified: false`, no minimums) so
  existing manifests do not break.
- **registry-discovery** — Apply the trust filter to every registry query.
  Surface `verified`, `installs`, `stars` in the discovery result so the CLI
  can render them. Reject unsafe skills with a typed `TrustError` listing
  which thresholds failed.
- **cli** — Add four subcommands:
  - `skillpod search <query>` — query the registry, render results as a
    table (or JSON), badge each row with whether it passes the active
    trust policy.
  - `skillpod outdated` — diff `skillfile.lock` commits against the latest
    commits the registry / git source advertises.
  - `skillpod update [skill]` — re-resolve and refresh the lockfile (all
    skills, or one).
  - `skillpod doctor` — verify manifest/lockfile/symlink consistency:
    every manifest skill is locked, every lockfile entry is materialised
    under `.skillpod/skills/`, every agent fan-out symlink resolves, and
    no rogue files exist under `.skillpod/skills/`.

## Impact

- New manifest keys; the loader gains validation rules but stays backwards
  compatible.
- New CLI surface (4 commands); no rename or removal of existing
  subcommands.
- Network behaviour: `search` and `outdated` are the first commands that
  *intentionally* hit the registry without an install side-effect.
- Specs touched: `manifest`, `registry-discovery`, `cli` (all MODIFIED;
  no new capabilities).

## Non-goals

- Signed skill packages or provenance attestation — separate future change.
- Allow-list / deny-list of specific skills by name — likely a future
  `add-skillpod-policy` change once we have real-world demand.
- Cross-source trust (e.g. trust signals from non-skills.sh registries) —
  out of scope until a second registry exists.
