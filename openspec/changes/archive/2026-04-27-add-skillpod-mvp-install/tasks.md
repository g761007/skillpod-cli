# Tasks — add-skillpod-mvp-install

## 1. Project bootstrap
- [x] 1.1 Create `pyproject.toml` (Python 3.11+, deps: typer, pydantic>=2, httpx, pyyaml; dev: pytest, ruff, mypy; entry point `skillpod = skillpod.cli:app`).
- [x] 1.2 Scaffold `src/skillpod/__init__.py` and the six sub-packages (`manifest/`, `lockfile/`, `sources/`, `registry/`, `installer/`, `cli/`), each with `__init__.py`.
- [x] 1.3 Add `.gitignore` entries for `.skillpod/`, `dist/`, `build/`, `__pycache__/`, `.venv/`. Keep `skillfile.yml` and `skillfile.lock` tracked.
- [x] 1.4 Configure `ruff` + `pytest` in `pyproject.toml`; add `tests/` with empty `conftest.py`.

## 2. Manifest capability
- [x] 2.1 Define pydantic models in `manifest/models.py`: `Skillfile`, `RegistryConfig`, `SourceEntry`, `SkillEntry`, `InstallPolicy`.
- [x] 2.2 Implement `manifest/loader.py:load(path)` reading YAML, normalising shorthand skill strings, applying defaults.
- [x] 2.3 Cross-field invariants enforced inside `models.py` via `@model_validator` (unique skill names, declared source references, supported agents).
- [x] 2.4 Unit tests: 20 scenarios covering minimal manifest, shorthand expansion, missing fields, malformed YAML, unknown keys, agent validation.

## 3. Lockfile capability
- [x] 3.1 Define `lockfile/models.py:Lockfile` and `LockedSkill` (source, url, commit, sha256).
- [x] 3.2 Implement `lockfile/io.py:read(path)` and `write(path, model)` using `safe_load` / `safe_dump`, deterministic key ordering.
- [x] 3.3 Implement `lockfile/integrity.py:hash_directory(path)` returning sorted-tree sha256.
- [x] 3.4 Unit tests: 15 scenarios — round-trip, missing file -> empty lockfile, hash stability, registry never persisted, local sources rejected.

## 4. Source-resolver capability
- [x] 4.1 Implement `sources/local.py` — verify path exists, return materialise target.
- [x] 4.2 Implement `sources/git.py` — clone into cache, resolve ref via `git rev-parse HEAD`, atomic temp-dir + rename for cache populate.
- [x] 4.3 Implement `sources/cache.py` — paths under `~/.cache/skillpod/<host>/<org>/<repo>@<commit>/`, env override `SKILLPOD_CACHE_DIR`, atomic rename for single-writer safety.
- [x] 4.4 Implement `sources/resolver.py:resolve_from_sources(skill, sources)` — priority-ordered probe + explicit-source override.
- [x] 4.5 Unit tests: 24 scenarios — local hit, git populate, cache reuse, priority, explicit source, URL parsing, error paths.

## 5. Registry-discovery capability
- [x] 5.1 Implement `registry/skills_sh.py:lookup(name)` — single GET to skills.sh, returning `RepoInfo(host, org, repo, ref, commit, meta)`.
- [x] 5.2 Wire registry as fallback in `installer/resolve.py` when no manifest source matches; resolver remains registry-free.
- [x] 5.3 Error mapping: HTTP non-2xx, network timeout, JSON decode error → typed `RegistryError` family.
- [x] 5.4 Tests with `respx` (httpx mock): 13 scenarios — 200 happy path, 404, 500, timeout, malformed payloads, GET-only contract.

## 6. Installer capability
- [x] 6.1 Implement `installer/pipeline.py:install(...)` orchestrating resolve → fetch → materialise → fan-out → write-lockfile.
- [x] 6.2 Implement `installer/fanout.py` with two helpers: `create_install_root_symlink` (owns `.skillpod/skills/`) and `create_managed_fanout_symlink` (refuses to overwrite unmanaged user symlinks).
- [x] 6.3 Frozen-mode + conflict detection inline in `pipeline.install`; `installer/errors.py` carries typed exceptions with stable exit codes.
- [x] 6.4 Integration test: 12 scenarios across local + git + registry-fallback + frozen-mode drift + rollback + conflict refusal + idempotency.

## 7. CLI capability
- [x] 7.1 `cli/app.py` — root `typer.Typer()` with `--manifest` and `--json` options shared via Annotated aliases on every subcommand.
- [x] 7.2 `cli/commands/init.py` — emit minimal `skillfile.yml`, append `.skillpod/` to `.gitignore` (idempotent).
- [x] 7.3 `cli/commands/install_cmd.py` — call installer pipeline; honour lockfile if present.
- [x] 7.4 `cli/commands/add.py` — snapshot manifest, append skill, install, restore on failure.
- [x] 7.5 `cli/commands/remove.py` — drop skill from manifest, uninstall, prune lockfile entry.
- [x] 7.6 `cli/commands/list_cmd.py` — print table or JSON with manifest skills + lockfile commits.
- [x] 7.7 `cli/commands/sync.py` — re-create symlinks from lockfile (cache-only path, no registry calls).
- [x] 7.8 Exit codes via `cli/_output.py:run_with_exit_codes` — `0` success / `1` user error / `2` system/network error.

## 8. End-to-end & docs
- [x] 8.1 `tests/_git_fixtures.py` builds throwaway git repos in `tmp_path`; covers both local and git skill fixtures inline (no separate offline bundle needed).
- [x] 8.2 E2E test in `tests/test_cli.py` runs `init` → `add` → `install` → `list` → `sync` against fixtures and asserts filesystem layout + lockfile contents.
- [x] 8.3 README.md quick-start references plan §14 ("discover → resolve → lock → install").
- [x] 8.4 `examples/skillfile.yml` mirrors plan §3.1.

## 9. Validation gate
- [x] 9.1 `openspec validate add-skillpod-mvp-install --strict` passes.
- [x] 9.2 `pytest -q` passes (99 unit + integration tests).
- [x] 9.3 Manual smoke: scratch project → `skillpod init`, hand-edit manifest with a local source, `skillpod install`, `skillpod list` — symlinks land under `.skillpod/skills/`, `.claude/skills/`, `.codex/skills/` as expected; local skill correctly omitted from `skillfile.lock`.
