# Launch Readiness Plan — public adoption (strangers)

> Goal: take skillpod from "the author uses it smoothly" to "a stranger can pick
> it up, succeed in 60 seconds, and trust it enough to adopt." Target milestone:
> **public promotion** (schema may still change pre-1.0).
>
> Date: 2026-06-23 · Baseline: v0.6.4 (433 tests, ruff + mypy strict, CI + PyPI live)

## Assessment summary

The project's *completeness* far exceeds its *discoverability + trustworthiness*.
The code is solid; strangers will stumble on small first-impression breaks
(`--version`) and on an unstated trust boundary (arbitrary git repos fanned into
agent context). Community infra (LICENSE, CONTRIBUTING, CODE_OF_CONDUCT,
SECURITY, examples) is already in place.

---

## Tier 0 — Launch blockers (small breaks that hurt first impressions)

- **T0.1 `--version` errors out.** No `--version` option exists; the first command
  a stranger types fails.
  → Add an eager `--version` callback on the main Typer callback (keep
  `no_args_is_help` behavior).
  → verify: `skillpod --version` prints `skillpod 0.6.4` and exits 0.
- **T0.2 Version drift.** `src/skillpod/__init__.py` hardcodes `0.5.6`; pyproject
  is `0.6.4`. Release CI already pins pyproject as the source of truth.
  → `__version__ = importlib.metadata.version("skillpod")` with a dev fallback.
  → verify: `python -c "import skillpod; print(skillpod.__version__)"` == pyproject.
- **T0.3 SECURITY.md stale.** Supported-version table says `0.5.x`.
  → Update to `0.6.x`.
  → verify: table reflects current minor.

## Tier 1 — First-time experience / time-to-first-value

- **T1.1 Shell completion is disabled** (`add_completion=False`).
  → Flip to `True`; gains `--install-completion` / `--show-completion` for free.
  → verify: `skillpod --show-completion` emits a completion script.
- **T1.2 No 60-second golden path.** `init` yields `skills: []`; README is 727
  lines. Strangers need a copy-paste 3-step path that ends in a *visible*
  fan-out into `.claude/skills/`.
  → Add a tight "Quickstart (60s)" block near the top of README.
  → verify: following the block from an empty dir produces a real skill dir.
- **T1.3 No demo GIF/asciinema.** (Human task — cannot be agent-automated.)
  → Record a short `init → add → list` cast; embed near the top of README.

## Tier 2 — Trust / safety (will a stranger dare to use it?)

skillpod pulls a stranger's `SKILL.md` into the agent's context — a supply-chain
surface. We don't need a sandbox; we need **honest disclosure** of the trust
boundary plus light transparency.

- **T2.1 git/local sources bypass trust policy.** `trust.py` only gates registry
  (skills.sh); `skillpod add owner/repo` pulls and fans out any repo unchecked.
  → Add a "Security model / what you're trusting" section to README that states
  this plainly (registry trust ≠ git/local trust; SKILL.md is read into agent
  context; pin commits via the lockfile).
  → verify: section exists and is accurate against `trust.py`.
- **T2.2 `add` transparency.** Human output shows only `(source_kind)`.
  → Surface the resolved `url@commit` in the human-readable `add` output so the
  user sees exactly what was pulled.
  → verify: `skillpod add <repo>` prints the source URL and short commit.
- **T2.3 (Phase 2, needs design) `skillpod audit`.** List installed skills with
  source + commit + SKILL.md summary so users can review what landed in their
  agents. New command → touches `app.py`; defer to avoid conflicting with T0.1.

## Tier 3 — Distribution / discoverability

- **T3.1 Highlight `--json` / CI-friendliness** in README (scriptability is an
  adoption lever for teams).
  → verify: README calls out `--json` as a first-class feature.
- **T3.2 (decision needed) PyPI long_description.** `readme = README.md` renders,
  but 727 lines is heavy on PyPI. Optional: a trimmed PyPI front page.

## Tier 4 — pre-1.0 honesty

- **T4.1 pre-1.0 notice** near the top of README: schema may break before 1.0.
  → verify: notice present and visible above the fold.

---

## Dispatch plan (conflict-free file partition)

- **Batch A — code polish** (files: `app.py`, `__init__.py`, `add.py`,
  `SECURITY.md`, tests): T0.1, T0.2, T0.3, T1.1, T2.2.
- **Batch B — docs** (files: `README.md` only): T1.2, T2.1, T3.1, T4.1, note T1.1.
- **Phase 2 (later, needs decisions / human):** T1.3 (GIF), T2.3 (`audit`), T3.2.

Gate after both batches: `uv run ruff check src tests`, `uv run mypy src/skillpod`,
`uv run pytest -q` all green before commit.
