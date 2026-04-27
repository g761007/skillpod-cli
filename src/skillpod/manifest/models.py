"""Pydantic models describing skillfile.yml.

The schema mirrors plans/skillpod-plan.md §3.1. Defaults are deterministic
so a manifest containing only `version: 1` and `skills: [audit]` loads
into a fully-formed `Skillfile`.

Trust-policy fields (`allow_unverified`, `min_installs`, `min_stars`) are
defined in `RegistrySkillsShPolicy` and nested under `RegistryConfig.skills_sh`
as part of `add-skillpod-trust-and-search` (Roadmap 0.2.0).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SUPPORTED_AGENTS: tuple[str, ...] = (
    "claude",
    "codex",
    "gemini",
    "cursor",
    "opencode",
    "antigravity",
)
"""Agents whose `<.agent>/skills/` directories may receive symlink fan-out."""


class _StrictModel(BaseModel):
    """Reject unknown keys so typos surface immediately."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RegistrySkillsShPolicy(_StrictModel):
    """Trust-policy knobs for the skills.sh registry.

    Nested under `RegistryConfig.skills_sh` (Roadmap 0.2.0,
    `add-skillpod-trust-and-search` §1 / manifest spec).

    Defaults preserve the 0.1.0 behaviour: allow only verified skills with
    no install or star minimums.

    Fields use ``strict=True`` so YAML string values such as ``"yes"`` or
    ``"1000"`` are rejected with a clear validation error instead of being
    silently coerced.
    """

    allow_unverified: Annotated[bool, Field(strict=True)] = False
    min_installs: Annotated[int, Field(strict=True)] = 0
    min_stars: Annotated[int, Field(strict=True)] = 0


class RegistryConfig(_StrictModel):
    """`registry:` block."""

    default: str = "skills.sh"
    skills_sh: RegistrySkillsShPolicy = Field(default_factory=RegistrySkillsShPolicy)


class SourceEntry(_StrictModel):
    """One entry under top-level `sources:`."""

    name: Annotated[str, Field(min_length=1)]
    type: Literal["local", "git"]
    path: str | None = None  # local
    url: str | None = None  # git
    ref: str = "main"  # git
    priority: int = 50

    @model_validator(mode="after")
    def _check_type_specific(self) -> SourceEntry:
        if self.type == "local":
            if not self.path:
                raise ValueError(f"source '{self.name}': type=local requires `path:`")
            if self.url:
                raise ValueError(f"source '{self.name}': type=local must not set `url:`")
        else:  # git
            if not self.url:
                raise ValueError(f"source '{self.name}': type=git requires `url:`")
            if self.path:
                raise ValueError(f"source '{self.name}': type=git must not set `path:`")
        return self


class SkillEntry(_StrictModel):
    """One entry under top-level `skills:`.

    Accepts shorthand strings via the loader's normaliser; the model itself
    is always the object form once loaded.
    """

    name: Annotated[str, Field(min_length=1)]
    source: str | None = None
    version: str | None = None  # commit-ish; resolved at install time


class InstallPolicy(_StrictModel):
    """`install:` block."""

    mode: Literal["symlink"] = "symlink"
    on_missing: Literal["error", "skip"] = "error"


class Skillfile(_StrictModel):
    """Top-level model for skillfile.yml v1."""

    version: Literal[1] = 1
    registry: RegistryConfig = Field(default_factory=RegistryConfig)
    agents: list[str] = Field(default_factory=list)
    install: InstallPolicy = Field(default_factory=InstallPolicy)
    sources: list[SourceEntry] = Field(default_factory=list)
    skills: list[SkillEntry] = Field(default_factory=list)

    @field_validator("agents")
    @classmethod
    def _agents_supported(cls, value: list[str]) -> list[str]:
        unknown = [a for a in value if a not in SUPPORTED_AGENTS]
        if unknown:
            raise ValueError(
                "unknown agent(s) "
                + ", ".join(repr(a) for a in unknown)
                + f"; supported: {', '.join(SUPPORTED_AGENTS)}"
            )
        if len(set(value)) != len(value):
            raise ValueError("agents list contains duplicates")
        return value

    @field_validator("sources")
    @classmethod
    def _source_names_unique(cls, value: list[SourceEntry]) -> list[SourceEntry]:
        names = [s.name for s in value]
        if len(set(names)) != len(names):
            raise ValueError("sources have duplicate `name`")
        return value

    @model_validator(mode="after")
    def _cross_check(self) -> Skillfile:
        skill_names = [s.name for s in self.skills]
        if len(set(skill_names)) != len(skill_names):
            raise ValueError("skills have duplicate `name`")

        source_names = {s.name for s in self.sources}
        for skill in self.skills:
            if skill.source is not None and skill.source not in source_names:
                raise ValueError(
                    f"skill '{skill.name}': unknown source '{skill.source}'; "
                    f"declared sources: {sorted(source_names) or '<none>'}"
                )
        return self


__all__ = [
    "SUPPORTED_AGENTS",
    "InstallPolicy",
    "RegistryConfig",
    "RegistrySkillsShPolicy",
    "SkillEntry",
    "Skillfile",
    "SourceEntry",
]
