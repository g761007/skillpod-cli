"""Pydantic models for a global profile file (~/.skillpod/profiles/<name>.yml).

A global profile file may carry per-skill **inline sources** so it can be
applied independently of any project:

```yaml
version: 1
profile:
  agents: [claude, codex]
  skills:
    - audit                       # bare string: name only
    - name: polish                # object form: inline source
      source: anthropics/skills   # git URL / owner/repo / local path
      ref: main                   # optional
      subpath: skills/polish      # optional (git)
```

The shared filter-mode :class:`~skillpod.manifest.models.ProfileEntry`
(name-only ``skills``) is intentionally left untouched; ``GlobalProfileFile``
exposes :meth:`GlobalProfileFile.as_profile_entry` to bridge back to it.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator

from skillpod.manifest.models import ProfileEntry


class GlobalProfileSkill(BaseModel):
    """One skill entry inside a global profile, optionally source-bearing."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str
    source: str | None = None  # inline spec: git URL / owner/repo / local path
    ref: str | None = None  # git ref (branch / tag / commit)
    subpath: str | None = None  # git-only: subdirectory within the source


class GlobalProfileBody(BaseModel):
    """The ``profile:`` body of a global profile file."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: str | None = None
    agents: list[str] = []
    skills: list[GlobalProfileSkill] = []

    @field_validator("skills", mode="before")
    @classmethod
    def _normalise_skills(cls, value: Any) -> Any:
        """Accept bare strings as a shorthand for ``{name: <string>}``."""
        if not isinstance(value, list):
            return value
        return [{"name": item} if isinstance(item, str) else item for item in value]

    @field_validator("skills")
    @classmethod
    def _skills_unique(
        cls, value: list[GlobalProfileSkill]
    ) -> list[GlobalProfileSkill]:
        names = [s.name for s in value]
        if len(set(names)) != len(names):
            raise ValueError("duplicate skill entries")
        return value

    @field_validator("agents")
    @classmethod
    def _agents_unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("duplicate agent entries")
        return value


class GlobalProfileFile(BaseModel):
    """Top-level wrapper for a standalone profile YAML file."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    version: Literal[1] = 1
    profile: GlobalProfileBody

    def as_profile_entry(self) -> ProfileEntry:
        """Project down to a name-only ``ProfileEntry`` for filter-mode callers."""
        return ProfileEntry(
            type=self.profile.type,
            agents=list(self.profile.agents),
            skills=[s.name for s in self.profile.skills],
        )


__all__ = ["GlobalProfileBody", "GlobalProfileFile", "GlobalProfileSkill"]
