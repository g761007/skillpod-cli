# skillpod

[![CI](https://github.com/danielhsieh/skillpod-cli/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/danielhsieh/skillpod-cli/actions/workflows/ci.yml)

> Pod-style dependency manager for AI coding agent skills.
> One declarative manifest, multi-agent fan-out.

skillpod is a **project-scoped, reproducible skill dependency manager** —
not a global skill installer.

```
discover → resolve → lock → install
```

- **Discover** skills from [skills.sh](https://skills.sh/).
- **Depend** on them with `skillfile.yml`.
- **Lock** them to a git commit in `skillfile.lock`.
- **Install** them once into `.skillpod/skills/` and fan out symlinks to
  every agent (`.claude/skills`, `.codex/skills`, `.gemini/skills`,
  `.cursor/skills`, `.opencode/skills`, `.antigravity/skills`).

## Status

Pre-release. The OpenSpec proposals describing the four roadmap milestones
live under [`openspec/changes/`](./openspec/changes). The original design
is at [`plans/skillpod-plan.md`](./plans/skillpod-plan.md).

## Quick start (planned)

```bash
skillpod init
skillpod add audit
skillpod install
```

## Continuous Integration

Every push and pull request against `master` runs two jobs:

**`test` (matrix: Python 3.11, 3.12 on ubuntu-latest)**

1. Install dependencies via `uv sync --frozen`
2. `uv run ruff check src tests` — lint
3. `uv run pytest -q` — full test suite
4. `uv run python -c "from skillpod.cli import app; print('cli imports OK')"` — CLI smoke test

**`openspec-validate` (single run, no matrix)**

Validates all four OpenSpec change proposals with `--strict`:
- `add-skillpod-mvp-install`
- `add-skillpod-trust-and-search`
- `add-skillpod-groups`
- `add-skillpod-adapter-layer`

The `openspec` CLI is installed via `npm install -g @fission-ai/openspec` (the package
that Homebrew's `openspec` formula wraps).

## Development

```bash
uv sync
uv run pytest -q
```
