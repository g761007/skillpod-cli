# Add per-agent adapter layer and copy/hardlink modes (Roadmap 0.4.0)

## Why

The MVP fan-out (`add-skillpod-mvp-install`) assumes every agent reads
*the same* skill bundle and that *every host can create symlinks*. Both
assumptions break in practice:

1. **Per-agent transformations.** Different agents look for different
   metadata files, slugs, or directory shapes. Today users solve this by
   hand-maintaining six near-identical copies. The plan §2.3 lists the
   six fan-out targets, but the plan §13 Roadmap acknowledges 0.4.0 needs
   an "adapter layer" so each target can be written with the right shape.
2. **Symlink-hostile environments.** Windows without dev-mode, certain CI
   runners, and some Docker overlays cannot create symlinks. The MVP
   pipeline aborts in those environments. We need `copy` and `hardlink`
   install modes as deterministic fallbacks.

This change introduces both mechanisms together because the adapter API
needs to know whether it is producing symlinks, copies, or hardlinks in
order to make sensible per-agent transforms.

## What Changes

- **installer** —
  - Extend `install.mode` to accept `symlink` (default) | `copy` |
    `hardlink`. Add `install.fallback: [copy]` so symlink mode can
    auto-degrade when the OS rejects a symlink.
  - Introduce an `Adapter` interface
    `adapt(skill_dir: Path, target_dir: Path, mode: InstallMode) -> None`.
    Ship a default `IdentityAdapter` matching MVP behaviour and a
    registry that maps `agent_id -> adapter`. Project authors can
    override per-agent adapters under
    `agents.<id>.adapter: <module.path>` in `skillfile.yml` (loader
    update lives in `manifest`, but is purely additive and bundled here
    via the installer requirements that consume the field).
- **cli** — Add `skillpod adapter list` to enumerate registered
  adapters and the `--agent <id>` flag on `skillpod sync` to re-fan-out
  for a single agent (used after switching install modes or changing
  adapters).

## Impact

- Existing manifests keep working: `install.mode` defaults to `symlink`,
  every agent uses `IdentityAdapter`, and `agents.<id>.adapter` is
  optional.
- New install modes change what appears under
  `.<agent>/skills/<name>` from a symlink to a directory tree (for
  `copy`) or a tree of hardlinks (for `hardlink`). `doctor` from
  `add-skillpod-trust-and-search` already tolerates both because it
  checks for "resolves into `.skillpod/skills/`" via path comparison
  rather than `os.path.islink`.
- Specs touched: `installer`, `cli` (both MODIFIED). Manifest gains the
  `agents.<id>.adapter` key but its behavioural contract lives in
  `installer`, so the manifest spec is not part of this change.

## Non-goals

- Bundling agent-specific adapters in the skillpod core. Adapters ship as
  small Python modules; users opt in by name. The default adapter is the
  identity transform, matching MVP behaviour for every agent.
- A general plugin loader for arbitrary CLI extensions; the adapter
  registry exists solely to satisfy the install-time transform contract.
- Schema freeze for v1 — that is a separate `freeze-skillpod-v1`
  governance change.
