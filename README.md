# skillpod

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

## Development

```bash
uv sync
uv run pytest -q
```
