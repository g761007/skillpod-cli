# Design — add-skillpod-mvp-install

## Stack & layout

- Python 3.11+ (uses `tomllib`, `StrEnum`, generic `TypedDict`).
- CLI: [Typer](https://typer.tiangolo.com/) — Click-derived, supports rich
  help and per-command options out of the box. Single `app = typer.Typer()`
  in `skillpod.cli:app`, registered as console script.
- Schema: [pydantic v2](https://docs.pydantic.dev/) — used for both
  `skillfile.yml` and `skillfile.lock` models. Pydantic gives us defaulting,
  validation, and JSON Schema export (useful for editor support later).
- HTTP: [httpx](https://www.python-httpx.org/) sync client (stdlib `http.client`
  is too low-level; we want connection pooling + redirects + JSON helpers).
- Git: invoked via `subprocess` calls to the system `git` binary. We
  deliberately avoid `gitpython` to keep dependencies slim and to behave
  identically to whatever the user's shell would produce.
- YAML: [PyYAML](https://pyyaml.org/) `safe_load` / `safe_dump`.

Source tree:

```
src/skillpod/
  __init__.py
  manifest/         # pydantic models, loader, validator
  lockfile/         # lockfile model, writer, integrity check
  sources/          # local + git resolver, cache layout
  registry/         # skills.sh client (read-only)
  installer/        # pipeline orchestrator + fan-out
  cli/              # Typer app, one module per subcommand
tests/
  fixtures/
    skill-local/    # sample skill on disk
    skill-git/      # sample skill in a throwaway git repo
  test_manifest.py
  test_lockfile.py
  test_sources.py
  test_registry.py
  test_installer.py
  test_cli_e2e.py
```

## Manifest schema (pydantic)

```python
class SkillEntry(BaseModel):
    name: str
    source: str | None = None     # name of a sources[] entry
    version: str | None = None    # commit-ish; resolved at install time

class SourceEntry(BaseModel):
    name: str
    type: Literal["local", "git"]
    path: str | None = None       # for local
    url: str | None = None        # for git
    ref: str = "main"             # for git
    priority: int = 50

class InstallPolicy(BaseModel):
    mode: Literal["symlink"] = "symlink"   # 0.1.0 only supports symlink
    on_missing: Literal["error", "skip"] = "error"

class RegistryConfig(BaseModel):
    default: str = "skills.sh"
    # trust-policy fields (allow_unverified, min_installs, min_stars)
    # land in change `add-skillpod-trust-and-search`. Not modelled here.

class Skillfile(BaseModel):
    version: int = 1
    registry: RegistryConfig = RegistryConfig()
    agents: list[str] = []           # claude / codex / gemini / cursor / opencode / antigravity
    install: InstallPolicy = InstallPolicy()
    sources: list[SourceEntry] = []
    skills: list[SkillEntry] = []    # shorthand strings normalised on load
```

`skills` accepts shorthand strings during `model_validate` via a custom
validator that wraps `"audit"` into `SkillEntry(name="audit")`.

## Lockfile schema (pydantic)

```yaml
version: 1
resolved:
  audit:
    source: git                  # always "git" in 0.1.0; "local" entries are not locked
    url: https://github.com/vercel-labs/agent-skills
    commit: abc1234...           # full 40-char sha
    sha256: ...                  # sha256 of skill contents at that commit
```

Registry name is intentionally absent. `local` sources are also absent —
local paths cannot be made reproducible across machines, so they are
recorded in the manifest only and replayed live each install.

## Resolution order

1. Read `skillfile.yml`.
2. Walk `skills[]`. For each entry:
   a. If `source:` set, look up that named source.
   b. Else, sort `sources[]` by priority desc and probe each (local: file
      exists; git: skill folder exists at ref).
   c. Else, query `skills.sh` to obtain a GitHub repo + ref + commit.
3. Fetch each resolved skill into the cache (git clone + checkout for
   commit; local sources are referenced in place).
4. Compare to `skillfile.lock` (if present); abort on mismatch.
5. Materialise `.skillpod/skills/<name>` (symlink to cache or local path).
6. For each agent in `agents[]`, create `<.agent>/skills/<name>` symlink
   targeting the entry under `.skillpod/skills/`.
7. Write/refresh `skillfile.lock`.

## Cache

```
~/.cache/skillpod/
  github.com/<org>/<repo>@<ref>/
    .git/
    <skill folders>
```

`<ref>` here is the resolved 40-char commit, not the user-visible ref.
Folders under cache are immutable: they are checked out once and never
mutated. Stale cache entries are GC-able by `skillpod cache prune`
(deferred — we just document `rm -rf ~/.cache/skillpod` as safe in 0.1.0).

## Symlink fan-out

`os.symlink(cache_or_local_path, .skillpod/skills/<name>)`, then
`os.symlink(.skillpod/skills/<name>, .<agent>/skills/<name>)`. A pre-flight
check verifies the agent target either does not exist or is already a
skillpod-managed symlink (i.e., target resides under `.skillpod/`); if it
points anywhere else, abort with `on_missing=error` semantics — we will not
silently overwrite hand-managed symlinks.

## What we explicitly skip in 0.1.0

- `copy` / `hardlink` install modes (-> 0.4.0)
- Trust policy, search, outdated, update, doctor (-> 0.2.0)
- Groups, user_skills priority, `global` CLI (-> 0.3.0)
- Per-agent adapter layer / Windows symlink fallback (-> 0.4.0)
- skill content static analysis (-> future)
