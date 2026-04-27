# Design — add-skillpod-adapter-layer

## Adapter contract

```python
class InstallMode(StrEnum):
    SYMLINK = "symlink"
    COPY    = "copy"
    HARDLINK = "hardlink"

class Adapter(Protocol):
    """Render `.skillpod/skills/<name>/` into `<.agent>/skills/<name>/`."""

    def adapt(
        self,
        *,
        skill_name: str,
        source_dir: Path,         # always .skillpod/skills/<name>/
        target_dir: Path,         # always .<agent>/skills/<name>/
        mode: InstallMode,
    ) -> None: ...
```

Contract details:

- The adapter MUST own the entire materialisation of `target_dir`. The
  installer guarantees `target_dir` does not exist when `adapt(...)` is
  called.
- The adapter MAY return early without creating `target_dir` if it
  determines the agent does not want this skill (e.g. agent-specific
  inclusion rules) — but it MUST log a structured reason so `doctor`
  can explain the absence later.
- The adapter MUST NOT touch `source_dir`. The installer treats
  `.skillpod/skills/<name>/` as the canonical, immutable source for the
  current install run.

## Install modes

| Mode | What ends up at `.<agent>/skills/<name>/` |
|---|---|
| `symlink` | a symbolic link to `.skillpod/skills/<name>/` (MVP default) |
| `copy` | a recursive copy of the directory tree |
| `hardlink` | a tree of files where each file is a hardlink, directories are real dirs |

`hardlink` mode requires `source_dir` and `target_dir` to be on the same
filesystem; the installer probes this with `os.stat().st_dev` and falls
back to `copy` (with a warning) if they diverge.

## Fallback

`install.fallback: [copy]` is the default for projects that opt into
`mode: symlink` on a host that cannot create symlinks (typical Windows
non-dev-mode error: `OSError: [WinError 1314]`). The fallback list is
ordered; the installer tries each entry and emits a structured warning
once it succeeds.

## Adapter registry

- Default registry maps every agent to `IdentityAdapter` (which simply
  performs the symlink/copy/hardlink dictated by `mode` — no
  transformation).
- Manifest extension: `agents.<id>.adapter: my_module.MyAdapter`. The
  installer imports the module at startup; import failure aborts the
  entire run with a clear error rather than silently falling back.
- Adapters are referenced by dotted path so users can ship their own
  adapter as a tiny side package; we are *not* providing a CLI to
  install adapters. They live wherever Python's import path can see
  them (typically a `skillpod_adapters` package the user adds to their
  project).

## CLI: `--agent <id>` on `sync`

Users running `skillpod sync --agent claude` re-render only the
`.claude/skills/...` tree. This is what people will do after switching
`mode` or pointing `agents.claude.adapter` at a new module. The flag
must be additive: if omitted, `sync` behaves exactly as it did in 0.1.0
(re-fan-out everything).

## What we are deferring further

- Pluggable file watchers / automatic re-fan-out on adapter file changes.
- A built-in registry of curated adapters per agent. We expect community
  adapters to materialise organically once the contract stabilises.
