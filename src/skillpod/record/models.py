"""Pydantic models for an install record (`installed.yml`).

A record answers **"what is installed on this machine right now"**. It is
descriptive, never prescriptive: nothing reads it to decide what *may* be
installed. That distinction is the whole point of replacing `skillfile.lock`,
whose entries were authoritative and sticky — see
`plans/2026-07-21-recommendation-model.md`.

Consequences of being a record rather than a lock:

- **Local sources are recorded.** The lockfile refused them because it could
  not pin them; a record has nothing to pin, it just states what is there.
- **`kind: unknown` is representable.** Skills whose origin cannot be
  recovered (installed before provenance was tracked, or moved in by
  `skillpod global archive`) are recorded honestly rather than omitted.
- **Never committed.** Both record files live under a `.skillpod/` directory,
  which `skillpod init` already adds to `.gitignore`.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_SHA1_HEX = re.compile(r"^[0-9a-f]{40}$")
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")

SkillKind = Literal["git", "registry", "local", "unknown"]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SkillRecord(_StrictModel):
    """One skill as actually materialised on this machine.

    ``ref`` records the branch or tag the install *followed*, so a later
    ``update`` knows what to re-resolve against. ``commit`` records what that
    ref pointed at when the install happened, so drift is detectable — but
    unlike a lockfile entry, nothing replays it.
    """

    kind: SkillKind
    source: str | None = None  # git URL, or an absolute path for local
    ref: str | None = None  # branch / tag followed at install time
    commit: str | None = None  # what `ref` resolved to (git / registry)
    subpath: str | None = None  # subdirectory within the source
    sha256: str | None = None  # content digest of the materialised directory

    @model_validator(mode="after")
    def _check_kind_consistency(self) -> SkillRecord:
        if self.kind in ("git", "registry"):
            if not self.source:
                raise ValueError(f"kind={self.kind} requires `source`")
            if not self.commit:
                raise ValueError(f"kind={self.kind} requires `commit`")
        elif self.kind == "local":
            if not self.source:
                raise ValueError("kind=local requires `source` (the directory path)")
            if self.commit:
                raise ValueError("kind=local must not set `commit`")
        else:  # unknown — provenance could not be recovered
            if self.source or self.commit or self.ref or self.subpath:
                raise ValueError(
                    "kind=unknown must not carry source/ref/commit/subpath; "
                    "record what is actually known instead"
                )

        if self.commit is not None and not _SHA1_HEX.fullmatch(self.commit):
            raise ValueError("commit must be a 40-character lowercase hex SHA")
        if self.sha256 is not None and not _SHA256_HEX.fullmatch(self.sha256):
            raise ValueError("sha256 must be a 64-character lowercase hex digest")
        return self


class InstallRecord(_StrictModel):
    """Top-level model for `installed.yml` v1."""

    version: Literal[1] = 1
    installed: dict[str, SkillRecord] = Field(default_factory=dict)


__all__ = ["InstallRecord", "SkillKind", "SkillRecord"]
