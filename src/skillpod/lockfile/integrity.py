"""Compute deterministic content digests for materialised skill directories.

The digest must be stable across runs and machines so that
`add-skillpod-mvp-install`'s frozen-mode check is reproducible. We hash:

1. The relative POSIX path of every regular file under `root` (sorted).
2. The byte contents of each file.
3. A separator byte `\\x00` between (path, content) pairs.

Symlinks are followed only when they point inside `root`; symlinks pointing
outside `root` are recorded by their literal target string instead of
following them, so cache locations cannot leak into the digest.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK = 1 << 16


def _iter_files(root: Path) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for path in root.rglob("*"):
        if path.is_dir() and not path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        out.append((rel, path))
    out.sort(key=lambda item: item[0])
    return out


def hash_directory(root: str | Path) -> str:
    """Return a 64-char lowercase hex sha256 digest of `root`'s contents."""
    root_path = Path(root)
    if not root_path.is_dir():
        raise FileNotFoundError(f"hash_directory: {root_path} is not a directory")

    digest = hashlib.sha256()
    for rel, path in _iter_files(root_path):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\x00")
        if path.is_symlink():
            target = path.readlink()
            digest.update(b"L")
            digest.update(str(target).encode("utf-8"))
        else:
            digest.update(b"F")
            with path.open("rb") as fh:
                while chunk := fh.read(_CHUNK):
                    digest.update(chunk)
        digest.update(b"\x00")
    return digest.hexdigest()


__all__ = ["hash_directory"]
