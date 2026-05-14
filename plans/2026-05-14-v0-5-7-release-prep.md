# Release v0.5.7 + Drop `openspec/` from git tracking

## Context

Branch `v0.5.7` is already committed (`b601288`) with the global list/link/unlink/verbose feature; tree is clean. This plan turns the branch into a formal release:

1. Bump packaging metadata, write CHANGELOG, prune stale references.
2. Stop tracking `openspec/` in git going forward (files stay on disk — past history untouched).
3. Tag, merge `v0.5.7 → main`, and let `release.yml` ship to PyPI.

User confirmed: `feedback_release_no_pr` applies — release goes straight to `main`, no PR; `openspec` should be removed from CONTRIBUTING.md and README; sdist `include` list also drops `"openspec"`.

---

## Files to modify

### 1. `pyproject.toml`
- L3: `version = "0.5.6"` → `version = "0.5.7"`
- L66–L79: drop `"openspec",` from `[tool.hatch.build.targets.sdist].include`

### 2. `CHANGELOG.md`
Insert a new `## [0.5.7] — 2026-05-14` section between `[Unreleased]` (L8) and `[0.5.6]` (L10). Content (sourced from commit `b601288` / branch summary):

```markdown
## [0.5.7] — 2026-05-14

### Added

- **`skillpod global link <name> [--agent ...]`** — fan-out an existing
  `~/.skillpod/skills/<name>` to agent dirs (`~/.<agent>/skills/<name>`) as
  symlinks, without re-fetching from source. `--yes/-y` replaces existing
  entries; omitting `--agent` links to every known agent
  (claude / codex / gemini / cursor / opencode / antigravity).
- **`skillpod global unlink <name> [--agent ...]`** — remove managed
  symlinks pointing into `~/.skillpod/skills/<name>`. Unmanaged entries
  (real directories or symlinks pointing elsewhere) are skipped with a
  warning, never overwritten.
- **`skillpod global list -v/--verbose`** — Unicode box card view per skill
  with description parsed from `SKILL.md` YAML frontmatter, ●/○ full-name
  agent indicators, human-readable size, and install path. Terminal width is
  capped at 100 cols for readability.
- Shared helper `paths.is_managed_global_fanout(name, agent_dir)` exposing
  the "is this agent entry a managed symlink into `~/.skillpod/skills/`"
  predicate for reuse across list / link / unlink / archive.

### Changed

- **`skillpod global list` default view now shows the install root**
  (`~/.skillpod/skills/`) as a compact NAME / LINKED / SIZE / MTIME table.
  `LINKED` shows `all`, `-`, or an abbreviated agent list
  (`cl,cx,ge,cu,oc,ag`). `MTIME` is date-only (`YYYY-MM-DD`). The previous
  per-agent fan-out view is preserved as `--agents/-a`.
- `installer.global_install._materialise_agent_link` promoted to public
  `materialise_agent_link` so the new `global link` command can reuse it.
- `global_archive` refactored to use the shared
  `is_managed_global_fanout` helper (−24 lines, no behaviour change).

### Removed

- `openspec/` is no longer tracked in git. The directory remains usable
  locally; its references in `README.md` (specs link) and `CONTRIBUTING.md`
  (workflow section) are removed.

### Internal

- 11 new tests covering global list (install-root / agents views), link,
  and unlink; 278 passed, 1 skipped on this branch.
- `mypy --strict` clean across 55 files.
```

Update reference links at the bottom (L284–L291):
- Replace `[Unreleased]: …compare/v0.5.6...HEAD` with `[Unreleased]: …compare/v0.5.7...HEAD`
- Insert `[0.5.7]: https://github.com/g761007/skillpod-cli/compare/v0.5.6...v0.5.7`

### 3. `README.md`
- L443 (Roadmap row for 0.5.7) — change status from `**current**` to `shipped`; drop the bolding. (No new "current" row yet; leave `1.0.0` as `planned`.)
- L452 — delete the `Specs: [openspec/specs/](./openspec/specs/).` line entirely (and its trailing newline so the section ends cleanly).

### 4. `CONTRIBUTING.md`
Remove the OpenSpec workflow section. Specifically:
- L38 — drop the `openspec/` line from the directory listing.
- L46–L60 (the "Spec-driven planning" subsection, including the heading) — delete the whole block. Make sure the surrounding section transitions still read naturally.

### 5. `.gitignore`
Append `openspec/` under the existing project-ignores group (after the `.skillpod/` line is the natural slot). Keep the trailing newline.

---

## Git operations (after file edits)

Run from repo root. All commands are reversible up to (but not including) the merge.

```bash
# 1. Stop tracking openspec/ (files stay on disk; history retained)
git rm -r --cached openspec/

# 2. Stage release artefacts
git add .gitignore pyproject.toml CHANGELOG.md README.md CONTRIBUTING.md

# 3. Single release commit on v0.5.7 branch
git commit -m "release: v0.5.7"

# 4. Tag the release (matches release.yml trigger `v*`)
git tag v0.5.7

# 5. Merge to main + push (per feedback_release_no_pr)
git checkout main
git merge --ff-only v0.5.7   # ff-only since v0.5.7 was branched from main
git push origin main
git push origin v0.5.7       # tag push triggers release.yml → PyPI
```

> If `--ff-only` rejects (someone else pushed to `main`), stop and surface the conflict — do not silently switch to a merge commit.

---

## Critical files

| Path | Why |
| --- | --- |
| `pyproject.toml` | version bump + sdist include trim |
| `CHANGELOG.md` | new 0.5.7 entry + compare links |
| `README.md` | roadmap row + drop broken openspec link |
| `CONTRIBUTING.md` | remove OpenSpec workflow section |
| `.gitignore` | add `openspec/` |
| `src/skillpod/cli/commands/global_link.py` | already shipped @ b601288 (reference) |
| `src/skillpod/cli/commands/global_unlink.py` | already shipped @ b601288 (reference) |
| `src/skillpod/cli/commands/global_list.py` | already shipped @ b601288 (reference) |
| `src/skillpod/installer/paths.py` | already shipped — `is_managed_global_fanout` lives here |
| `.github/workflows/release.yml` | PyPI publish via OIDC; fires on `v*` tag push |

---

## Verification

After edits, before the merge:

```bash
# Tree state
git status                                # only the 5 expected files staged
git ls-files openspec | wc -l             # → 0 (openspec untracked)
ls openspec/ | head                       # local files still present

# Packaging sanity
grep '^version' pyproject.toml            # → version = "0.5.7"
grep -n openspec pyproject.toml           # no match (include list cleaned)
head -20 CHANGELOG.md                     # 0.5.7 entry first, above 0.5.6

# Test gate (already green @ b601288, re-run for the release commit)
uv run mypy src/skillpod
uv run pytest -q
uv run ruff check src tests
```

After the merge + tag push:
- GitHub Actions `release.yml` should fire on `v0.5.7` and publish to PyPI via OIDC.
- `pip install --upgrade skillpod` resolves to `0.5.7`.
