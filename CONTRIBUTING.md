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
  record/          installed.yml — what is materialised, per scope
  integrity.py     deterministic content digests
  sources/         git / github / skills.sh resolvers
  registry/        skills.sh discovery
  installer/       materialise into .skillpod/ + adapter fan-out
  cli/             typer commands
tests/             pytest mirror of the above
examples/          minimal skillfile.yml used by docs
```

The codebase mirrors the **discover → resolve → lock → install** flow.
When adding behaviour, prefer extending the matching capability rather than
introducing a new top-level package.

## Commit messages

Conventional Commits — `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
For roadmap milestones the convention has been `feat(<version>): <summary>`,
e.g. `feat(0.4.0): adapter layer + copy/hardlink modes`.

## Pull requests

- Branch from `main`.
- Keep PRs focused; one capability or one fix at a time.
- All CI checks (lint, mypy, pytest on Linux/macOS/Windows) must be green
  before merge.
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
