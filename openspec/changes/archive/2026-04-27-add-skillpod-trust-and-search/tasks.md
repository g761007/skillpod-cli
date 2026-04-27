# Tasks — add-skillpod-trust-and-search

## 1. Manifest extension
- [x] 1.1 Add `RegistrySkillsShPolicy(allow_unverified: bool = False, min_installs: int = 0, min_stars: int = 0)` model and nest under `RegistryConfig.skills_sh`.
- [x] 1.2 Update loader to accept the new keys; ensure existing manifests without the block still parse.
- [x] 1.3 Tests: missing block uses defaults; explicit block round-trips; invalid types rejected (strict mode rejects YAML coercion).

## 2. Registry trust filter
- [x] 2.1 Extend `RepoInfo` with `verified: bool`, `installs: int`, `stars: int`, populated from registry payload `meta`.
- [x] 2.2 Implement `registry/trust.py:enforce(policy, repo_info)` returning `repo_info` or raising `TrustError(reasons=[...])` listing every failed threshold.
- [x] 2.3 Wire the filter into `installer/resolve.py` (the only caller that mutates project state); `search` calls `enforce` separately to compute the `passes-policy` badge without aborting.
- [x] 2.4 Tests: policy passes, policy fails on each individual threshold, defaults equivalent to "allow anything verified", multi-failure aggregation.

## 3. `skillpod search`
- [x] 3.1 `cli/commands/search.py` — accept `<query>`, optional `--limit/-n`, share `--json` and `--manifest` flags.
- [x] 3.2 Render table rows `name | repo | installs | stars | verified | passes-policy`.
- [x] 3.3 Tests with `respx`: 0 results, single-row pass, single-row fail, JSON shape stable. (MVP: query is treated as exact skill name pending a real list endpoint — documented in module docstring.)

## 4. `skillpod outdated`
- [x] 4.1 `cli/commands/outdated.py` — uniform `git ls-remote --exit-code <url> HEAD` for every lockfile entry (lockfile does not record source kind; ls-remote works for both registry- and explicit-git-sourced URLs).
- [x] 4.2 Output rows `name | locked | latest | drift`.
- [x] 4.3 Exit `0` for both clean and drift cases (informational); `2` on `git ls-remote` failure.
- [x] 4.4 Tests: drift detected, no drift, ls-remote failure.

## 5. `skillpod update`
- [x] 5.1 `cli/commands/update.py` — accept optional `<skill>`; without it updates all.
- [x] 5.2 Force re-resolve mode: snapshot lockfile, drop matching entries, run installer pipeline; trust enforcement still applies through the wired hook in §2.3.
- [x] 5.3 Trust policy enforced on update via the same code path as install.
- [x] 5.4 Tests: single-skill update; trust failure aborts with code 1 and rolls back.

## 6. `skillpod doctor`
- [x] 6.1 `cli/commands/doctor.py` — four checks: (a) manifest skill present in lockfile (skipping local), (b) lockfile entry materialised, (c) fan-out symlink resolves into `.skillpod/skills/`, (d) orphan dirs under `.skillpod/skills/`.
- [x] 6.2 Findings carry `severity ∈ {error, warning}`, `code`, `message`, optional `path`.
- [x] 6.3 Exit `0` clean (warnings allowed), `1` any error-severity finding, `2` filesystem unreadable.
- [x] 6.4 Tests: clean repo, missing symlink, orphan dir, lockfile drift.

## 7. Validation gate
- [x] 7.1 `openspec validate add-skillpod-trust-and-search --strict` passes.
- [x] 7.2 `pytest -q` passes — **131 tests, +32 over MVP** (was 99).
- [x] 7.3 Manual smoke: scratch project → install local skill → `skillpod doctor` shows clean; create stray dir under `.skillpod/skills/` → `doctor` flags it as `warning` and exits 0; `outdated` correctly handles a lockfile with zero git entries; `search --help` exposes `--limit/-n` + `--json`.
