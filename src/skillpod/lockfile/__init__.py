"""Lockfile capability: skillfile.lock schema and I/O.

Content hashing moved to :mod:`skillpod.integrity` — it is consumed by
fan-out and global install, which have nothing to do with the lockfile.
"""

from skillpod.lockfile.io import LockfileError, read, write
from skillpod.lockfile.models import LockedSkill, Lockfile

__all__ = [
    "LockedSkill",
    "Lockfile",
    "LockfileError",
    "read",
    "write",
]
