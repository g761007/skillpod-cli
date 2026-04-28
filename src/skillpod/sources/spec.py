"""Parse a positional `add` argument into a source specification.

The `skillpod add` command accepts either a bare skill name (legacy
behaviour: resolved against declared sources or registry) or a source
identifier (git URL / GitHub `owner/repo` shorthand / local path).

`parse_source_spec(text)` returns a `SourceSpec` for source-shaped
inputs and `None` for bare skill names — the CLI dispatches on that.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

_GITHUB_SHORTHAND = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")

# Matches browser-style tree URLs from GitHub/GitLab/Bitbucket:
#   https://<host>/<owner>/<repo>/tree/<ref>[/<subpath>]
#   https://<host>/<owner>/<repo>/-/tree/<ref>[/<subpath>]  (GitLab)
_DEEP_URL = re.compile(
    r"(https?://[^/?#\s]+/[^/?#\s]+/[^/?#\s]+)"
    r"/(?:-/)?tree"
    r"/([^/?#\s]+)"
    r"(?:/(.+))?"
)


@dataclass(frozen=True)
class SourceSpec:
    """Canonical form of a source identifier passed to `skillpod add`.

    ``ref`` is ``None`` when the user did not pass ``--ref``; the resolver
    then queries the remote's default branch (e.g. ``main`` or ``master``)
    and rewrites the spec with the concrete branch name before any caller
    persists it to ``skillfile.yml``.

    ``subpath`` is set when the input was a browser tree URL pointing at a
    subdirectory within the repo (e.g. ``/tree/main/skills/foo``).  The
    installer uses it as the root for discovery instead of the repo root.
    """

    kind: Literal["git", "local"]
    url_or_path: str
    derived_name: str
    ref: str | None = None
    subpath: str | None = None  # git-only: subdirectory within the cloned repo


def _strip_dotgit(name: str) -> str:
    return name[: -len(".git")] if name.endswith(".git") else name


def _name_from_url(url: str) -> str:
    """Last path segment of `url`, with any `.git` suffix removed."""
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    if ":" in tail and "/" not in tail:
        # SCP-style "git@github.com:org/repo.git" hits here only when the
        # whole URL has no `/` — should not happen, but be defensive.
        tail = tail.rsplit(":", 1)[-1]
    return _strip_dotgit(tail) or "source"


def _parse_deep_url(
    text: str,
) -> tuple[str, str, str | None, str] | None:
    """Parse a browser tree URL into ``(clone_url, ref, subpath, derived_name)``.

    Returns ``None`` when ``text`` is not a recognised tree URL.
    """
    m = _DEEP_URL.fullmatch(text.rstrip("/"))
    if m is None:
        return None
    clone_url = _strip_dotgit(m.group(1))
    ref = m.group(2)
    subpath: str | None = m.group(3) or None
    name = subpath.rsplit("/", 1)[-1] if subpath else _name_from_url(clone_url)
    return clone_url, ref, subpath, name


def parse_source_spec(text: str, *, ref: str | None = None) -> SourceSpec | None:
    """Return a SourceSpec if `text` looks like a source, else None.

    Detection rules (first match wins):

    1. `git@host:org/repo[.git]` — SCP-style SSH git URL
    2. Contains `://` — full URL (https/http/ssh/git/file)
    3. Ends with `.git` — bare git URL
    4. Starts with `./`, `../`, `/`, `~` — filesystem path
    5. Matches `^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$` — GitHub shorthand
       (expanded to `https://github.com/<text>`)
    6. Otherwise → bare skill name (returns None)
    """
    candidate = text.strip()
    if not candidate:
        return None

    if candidate.startswith("git@"):
        # SCP-style: git@github.com:org/repo[.git]
        _, _, after_at = candidate.partition("@")
        _, _, path = after_at.partition(":")
        return SourceSpec(
            kind="git",
            url_or_path=candidate,
            derived_name=_name_from_url(path) if path else _name_from_url(candidate),
            ref=ref,
        )

    if "://" in candidate:
        deep = _parse_deep_url(candidate)
        if deep is not None:
            clone_url, tree_ref, subpath, name = deep
            return SourceSpec(
                kind="git",
                url_or_path=clone_url,
                derived_name=name,
                # explicit --ref overrides the ref embedded in the tree URL
                ref=ref if ref is not None else tree_ref,
                subpath=subpath,
            )
        return SourceSpec(
            kind="git",
            url_or_path=candidate,
            derived_name=_name_from_url(candidate),
            ref=ref,
        )

    if candidate.endswith(".git"):
        return SourceSpec(
            kind="git",
            url_or_path=candidate,
            derived_name=_name_from_url(candidate),
            ref=ref,
        )

    if candidate.startswith(("./", "../", "/", "~")):
        expanded = str(Path(candidate).expanduser())
        return SourceSpec(
            kind="local",
            url_or_path=expanded,
            derived_name=_name_from_url(expanded),
            ref=ref,
        )

    if _GITHUB_SHORTHAND.fullmatch(candidate):
        url = f"https://github.com/{candidate}"
        return SourceSpec(
            kind="git",
            url_or_path=url,
            derived_name=_name_from_url(candidate),
            ref=ref,
        )

    return None


def derive_unique_name(base: str, existing: set[str]) -> str:
    """Suffix `-2`, `-3`, ... onto `base` until the name is unique."""
    if base not in existing:
        return base
    i = 2
    while True:
        candidate = f"{base}-{i}"
        if candidate not in existing:
            return candidate
        i += 1


__all__ = ["SourceSpec", "derive_unique_name", "parse_source_spec"]
