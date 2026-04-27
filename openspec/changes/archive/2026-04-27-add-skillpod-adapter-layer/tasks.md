# Tasks — add-skillpod-adapter-layer

## 1. Install mode plumbing
- [x] 1.1 Extend `InstallPolicy.mode` Literal to `{symlink, copy, hardlink}`. Add `fallback: list[Literal["copy"]] = ["copy"]`.
- [x] 1.2 Loader: backward-compat parsing — manifests authored before this change still load with mode=symlink and fallback=[copy].
- [x] 1.3 Tests: each mode round-trips; unknown mode rejected.

## 2. Adapter interface and default
- [x] 2.1 Define `installer/adapter.py:Adapter` protocol and `InstallMode` enum.
- [x] 2.2 Implement `installer/adapter_default.py:IdentityAdapter` covering all three modes.
- [x] 2.3 Define adapter registry in `installer/adapter_registry.py`; default mapping is `{agent_id: IdentityAdapter for every supported agent}`.
- [x] 2.4 Tests for `IdentityAdapter`: symlink (already covered by MVP), copy creates independent tree, hardlink shares inodes when same FS.

## 3. Manifest hook
- [x] 3.1 Extend manifest loader to accept `agents.<id>.adapter: dotted.path`. (Implementation lives here even though no spec change is filed in `manifest`; the contract for use is in `installer`.)
- [x] 3.2 Validate `agents.<id>` shape — either bare string `claude` (legacy) or `{ name: claude, adapter: pkg.MyAdapter }`.
- [x] 3.3 Resolve adapter at startup; import error aborts the run with a typed `AdapterImportError`.
- [x] 3.4 Tests: bare-string legacy form still loads; object form imports adapter; import error reported.

## 4. Cross-FS / fallback handling
- [x] 4.1 Implement filesystem device probe before hardlink fan-out; on mismatch, downgrade to `copy` and emit a warning.
- [x] 4.2 Implement `install.fallback` chain when `os.symlink` raises `OSError` (Windows-style symlink rejection); first successful mode wins; emit a single warning naming the chosen mode.
- [x] 4.3 Tests: simulated `os.symlink` raise -> falls back to `copy`; cross-device hardlink probe -> falls back; fallback list of `[]` aborts cleanly.

## 5. CLI updates
- [x] 5.1 `cli/commands/adapter.py`: `skillpod adapter list` prints the active registry as `agent | adapter | mode-supported`.
- [x] 5.2 Extend `cli/commands/sync.py` with `--agent <id>` to re-fan-out only that agent. Default behaviour unchanged.
- [x] 5.3 Tests: `adapter list` JSON shape; `sync --agent claude` only modifies `.claude/skills/`, leaves others untouched.

## 6. Validation gate
- [x] 6.1 `openspec validate add-skillpod-adapter-layer --strict` passes.
- [x] 6.2 `pytest -q` passes including the new adapter, mode, and fallback tests.
- [x] 6.3 Manual: in a Linux VM, install with `mode: copy`; in macOS, install with `mode: hardlink` and confirm `.claude/skills/<n>/<file>` shares the same inode as `.skillpod/skills/<n>/<file>`. *(Superseded by Phase 6 CI OS matrix in 0.5.0; manual VM step deferred to release-candidate dry runs.)*
