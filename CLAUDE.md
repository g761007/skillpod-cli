# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv sync                              # install / sync dependencies
uv run pytest -q                     # run all tests
uv run pytest tests/test_foo.py      # single test file
uv run pytest -k test_name           # single test function
uv run ruff check src tests          # lint
uv run mypy src/skillpod             # type check (strict)
```

## Architecture

**Entry point:** `skillpod = "skillpod.cli:app"` — a [Typer](https://typer.tiangolo.com/) app with ~14 sub-commands spread across `src/skillpod/cli/commands/`.

**Install pipeline** (the core data flow):

```
skillfile.yml
  → manifest/         Pydantic models; parse + validate
  → sources/          Resolve each skill to a commit+URL
      git.py          git ls-remote → clone → atomic rename into immutable cache
      discovery.py    Scan SKILL.md files; supports multi-skill repos and root-is-skill repos
      resolver.py     Priority-ordered source probing; explicit source bypasses probing
  → installer/
      fanout.py       Materialise .skillpod/skills/<name>/ as a real directory (not a symlink)
      adapter.py      Fan-out copies/symlinks/hardlinks into .<agent>/skills/<name>/
      pipeline.py     Orchestrates all steps; rolls back on failure
  → lockfile/         SHA-256 per skill; YAML serialisation + integrity checks
```

**Key design decisions:**
- `~/.cache/skillpod/` is an **immutable git cache** (atomic rename prevents partial clones).
- `.skillpod/skills/` is always a **real directory** (`shutil.copytree`), never a symlink — survives cache clears.
- `SourceSpec.ref = None` means auto-detect via `git ls-remote --symref HEAD`; the resolved ref is written into the lockfile.
- Adapter fan-out strategy (symlink / copy / hardlink) is governed by `install.mode` in `skillfile.yml`.
- `sources.discovery` honours a `root_name` parameter so a single-skill repo (`SKILL.md` at root) gets a meaningful name without coupling it to the cache directory basename.

**Module map (brief):**

| Package | Responsibility |
|---|---|
| `cli/` | Command wiring; user-facing I/O; reads manifest + calls installer |
| `manifest/` | `skillfile.yml` Pydantic models; sources, skills, groups, agents, registry policy |
| `sources/` | git clone/fetch, local directory scan, registry HTTP (skills.sh), priority resolver |
| `installer/` | pipeline, adapter protocol, fanout materialisation |
| `lockfile/` | lock model, SHA-256 integrity, YAML read/write |
| `registry/` | skills.sh search client; trust-policy filtering |

## Testing conventions

- Shared fixtures live in `tests/conftest.py`; git repo fixtures in `tests/_git_fixtures.py`.
- HTTP calls to skills.sh are mocked with **respx**.
- `make_skill_repo()` and `make_root_skill_repo()` helpers build in-memory bare repos for git source tests.
