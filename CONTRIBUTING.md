# Contributing to skillpod

Thanks for your interest in skillpod. Bug reports, feature requests, and
pull requests are all welcome.

## Development environment

skillpod is a Python 3.11+ project managed with [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/g761007/skillpod-cli.git
cd skillpod-cli
uv sync
uv run pytest -q
```

Useful commands:

| Command | What it does |
| --- | --- |
| `uv run pytest -q` | full test suite |
| `uv run ruff check src tests` | lint |
| `uv run ruff format src tests` | format |
| `uv run mypy src/skillpod` | strict type-check |
| `uv build` | build the sdist + wheel into `dist/` |

## Project layout

```
src/skillpod/
  manifest/        skillfile.yml schema (pydantic v2)
  lockfile/        skillfile.lock pinned to git commits
  sources/         git / github / skills.sh resolvers
  registry/        skills.sh discovery
  installer/       materialise into .skillpod/ + adapter fan-out
  cli/             typer commands
tests/             pytest mirror of the above
openspec/          spec-driven planning artifacts
examples/          minimal skillfile.yml used by docs
```

The codebase mirrors the **discover → resolve → lock → install** flow.
When adding behaviour, prefer extending the matching capability rather than
introducing a new top-level package.

## Spec-driven changes (OpenSpec)

Non-trivial changes are planned through [OpenSpec](https://openspec.dev/) before
code lands. The flow:

1. `openspec` (or the `openspec-new-change` skill) — create a `proposal.md`,
   `tasks.md`, optional `design.md`, and delta `specs/`.
2. Implement the tasks; tick them off in `tasks.md`.
3. `openspec validate <change> --strict` (CI also runs this).
4. `openspec archive <change> -y` once everything is implemented; archived
   changes live under `openspec/changes/archive/YYYY-MM-DD-<name>/` and the
   delta specs are merged into `openspec/specs/`.

`openspec/config.yaml` documents the conventions (every requirement needs at
least one `#### Scenario:` block, capability names stay stable, etc.).

For tiny fixes (typos, single-line bugs) you can skip OpenSpec and submit the
PR directly.

## Commit messages

Conventional Commits — `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
For roadmap milestones the convention has been `feat(<version>): <summary>`,
e.g. `feat(0.4.0): adapter layer + copy/hardlink modes`.

## Pull requests

- Branch from `main`.
- Keep PRs focused; one capability or one fix at a time.
- All CI checks (lint, mypy, pytest on Linux/macOS/Windows, OpenSpec validate)
  must be green before merge.
- Update `CHANGELOG.md` under `[Unreleased]` for any user-visible change.

## Releasing

Release artifacts are produced by `.github/workflows/release.yml` when a
`v*` tag is pushed. The workflow uses **PyPI Trusted Publisher (OIDC)** —
no API token required.

```bash
# bump pyproject.toml + CHANGELOG.md, commit
git tag v0.6.0
git push origin v0.6.0
```

## Code of conduct

By participating in this project you agree to abide by the
[Code of Conduct](./CODE_OF_CONDUCT.md).
