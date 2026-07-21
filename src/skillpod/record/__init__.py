"""Install records: what is materialised on this machine, per scope.

Two files, same schema:

- ``<project>/.skillpod/installed.yml`` — this project's skills
- ``~/.skillpod/installed.yml`` — the global skill set

Both are local and gitignored. Neither constrains what may be installed;
they only state what *is*. See :mod:`skillpod.record.models`.
"""

from skillpod.record.io import RecordError, read, write
from skillpod.record.models import InstallRecord, SkillKind, SkillRecord

__all__ = [
    "InstallRecord",
    "RecordError",
    "SkillKind",
    "SkillRecord",
    "read",
    "write",
]
