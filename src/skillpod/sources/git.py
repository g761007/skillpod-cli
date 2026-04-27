"""Resolve a `git` source — clone + checkout into the immutable cache.

Strategy:

1. Compute desired commit by ``git ls-remote <url> <ref>`` (or, if the ref
   is already a 40-char SHA, take it as-is).
2. If the cache directory for that commit already exists, return it
   (immutable cache hit — no git invocations beyond ls-remote).
3. Otherwise clone into a sibling staging directory, check out the
   commit, then atomically ``rename()`` the staging dir into place.
   If the destination already exists at rename time (race with another
   installer), discard the staging dir and use the existing cache entry.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from skillpod.manifest.models import SourceEntry
from skillpod.sources import cache as cache_mod
from skillpod.sources.errors import GitOperationError, SourceError
from skillpod.sources.types import ResolvedSkill

_SHA1 = re.compile(r"^[0-9a-f]{40}$")


def _run_git(*args: str, cwd: Path | None = None) -> str:
    try:
        result = subprocess.run(
            ("git", *args),
            cwd=cwd,
            check=True,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:  # pragma: no cover - depends on env
        raise GitOperationError("git executable not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise GitOperationError(
            f"git {' '.join(args)} failed (exit {exc.returncode}): {exc.stderr.strip()}"
        ) from exc
    return result.stdout


def resolve_ref(url: str, ref: str) -> str:
    """Return the 40-character commit SHA that ``ref`` resolves to in ``url``."""
    if _SHA1.fullmatch(ref):
        return ref
    output = _run_git("ls-remote", "--exit-code", url, ref)
    first_line = output.strip().splitlines()[0] if output.strip() else ""
    sha, _, _ = first_line.partition("\t")
    if not _SHA1.fullmatch(sha):
        raise GitOperationError(f"git ls-remote returned no SHA for {ref!r} in {url!r}")
    return sha


def populate_cache(url: str, commit: str) -> Path:
    """Ensure the cache contains ``<url>@<commit>``; return its path."""
    target = cache_mod.cache_path_for(url, commit)
    if target.exists():
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    staging = cache_mod.staging_dir(commit)
    if staging.exists():
        shutil.rmtree(staging)
    staging.parent.mkdir(parents=True, exist_ok=True)

    try:
        _run_git("clone", "--quiet", url, str(staging))
        _run_git("checkout", "--quiet", commit, cwd=staging)
        # Verify HEAD matches what we asked for; otherwise abort cleanly.
        head = _run_git("rev-parse", "HEAD", cwd=staging).strip()
        if head != commit:
            raise GitOperationError(
                f"checkout HEAD ({head}) does not match requested commit ({commit})"
            )
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    try:
        staging.rename(target)
    except OSError:
        if target.exists():
            # Another installer beat us to it — fine.
            shutil.rmtree(staging, ignore_errors=True)
        else:  # pragma: no cover - true OS errors are rare in tests
            shutil.rmtree(staging, ignore_errors=True)
            raise
    return target


def resolve_git(
    skill_name: str,
    source: SourceEntry,
    *,
    explicit_commit: str | None = None,
) -> ResolvedSkill:
    """Resolve ``skill_name`` against a `git` source.

    ``explicit_commit`` lets the installer skip the ls-remote step when
    a lockfile already pins a commit.
    """
    if source.type != "git":
        raise SourceError(f"resolve_git called for non-git source {source.name!r}")
    if not source.url:
        raise SourceError(f"git source {source.name!r} is missing `url:`")

    commit = explicit_commit or resolve_ref(source.url, source.ref)
    repo_root = populate_cache(source.url, commit)
    skill_dir = repo_root / skill_name
    if not skill_dir.is_dir():
        raise SourceError(
            f"git source {source.name!r}: skill {skill_name!r} not present at "
            f"{source.url}@{commit} (looked for {skill_dir})"
        )

    return ResolvedSkill(
        name=skill_name,
        source_kind="git",
        source_name=source.name,
        path=skill_dir.resolve(),
        url=source.url,
        commit=commit,
    )


__all__ = ["populate_cache", "resolve_git", "resolve_ref"]
