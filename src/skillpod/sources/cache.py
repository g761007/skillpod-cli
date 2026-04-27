"""Global immutable cache layout for git-resolved skills.

Layout (per `source-resolver/spec.md`):

    ~/.cache/skillpod/<host>/<org>/<repo>@<commit>/

The cache root is configurable via the environment variable
``SKILLPOD_CACHE_DIR`` so tests can sandbox it.

Cache contents are treated as immutable — once a `<…>@<commit>` directory
exists, no caller writes inside it again. Populating runs through a
temp-dir-then-rename so concurrent installers cannot leave a half-cloned
working tree behind.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse

_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_TMP_SUBDIR = ".tmp"


def cache_root() -> Path:
    """Return the global cache root."""
    env = os.environ.get("SKILLPOD_CACHE_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".cache" / "skillpod"


def parse_repo_url(url: str) -> tuple[str, str]:
    """Return ``(host, repo_path)`` for HTTPS, SSH, or file:// git URLs.

    The returned `repo_path` has any trailing ``.git`` stripped and uses
    forward slashes regardless of platform.
    """
    if url.startswith(("http://", "https://", "ssh://", "git://", "file://")):
        parsed = urlparse(url)
        host = parsed.hostname or parsed.netloc or "localhost"
        path = parsed.path.lstrip("/")
    elif "@" in url and ":" in url and not url.startswith("/"):
        # SCP-style:  git@github.com:org/repo.git
        user_host, _, path = url.partition(":")
        _, _, host = user_host.partition("@")
        if not host:
            host = user_host
    else:
        # Treat as a filesystem path (used in tests).
        host = "_local"
        path = url.lstrip("/")

    if path.endswith(".git"):
        path = path[: -len(".git")]
    if not path:
        raise ValueError(f"cannot derive cache path from URL: {url!r}")
    return host, path


def cache_path_for(url: str, commit: str) -> Path:
    """Compute the canonical cache directory for ``(url, commit)``."""
    if not _SHA1.fullmatch(commit):
        raise ValueError("commit must be a 40-character lowercase hex SHA")
    host, repo_path = parse_repo_url(url)
    return cache_root() / host / f"{repo_path}@{commit}"


def staging_dir(commit: str) -> Path:
    """Return a temp directory under the cache root for in-flight clones."""
    return cache_root() / _TMP_SUBDIR / f"clone-{commit}-{os.getpid()}"


__all__ = ["cache_path_for", "cache_root", "parse_repo_url", "staging_dir"]
