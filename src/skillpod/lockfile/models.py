"""Pydantic models for skillfile.lock.

Per `lockfile/spec.md`:
- Only git-resolved skills are stored. `local` sources are never locked.
- Registry name (e.g. `skills.sh`) is never stored — only the underlying
  git source data.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SHA1_HEX = re.compile(r"^[0-9a-f]{40}$")
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LockedSkill(_StrictModel):
    """A single resolved skill pinned to an immutable git commit."""

    source: Literal["git"] = "git"
    url: Annotated[str, Field(min_length=1)]
    commit: Annotated[str, Field(min_length=40, max_length=40)]
    sha256: Annotated[str, Field(min_length=64, max_length=64)]

    @field_validator("commit")
    @classmethod
    def _commit_is_full_sha1(cls, value: str) -> str:
        if not _SHA1_HEX.fullmatch(value):
            raise ValueError("commit must be a 40-character lowercase hex SHA")
        return value

    @field_validator("sha256")
    @classmethod
    def _sha256_is_hex(cls, value: str) -> str:
        if not _SHA256_HEX.fullmatch(value):
            raise ValueError("sha256 must be a 64-character lowercase hex digest")
        return value


class Lockfile(_StrictModel):
    """Top-level model for skillfile.lock v1."""

    version: Literal[1] = 1
    resolved: dict[str, LockedSkill] = Field(default_factory=dict)


__all__ = ["LockedSkill", "Lockfile"]
