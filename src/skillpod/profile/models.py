"""Pydantic model for a global profile file (~/.skillpod/profiles/<name>.yml)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from skillpod.manifest.models import ProfileEntry


class GlobalProfileFile(BaseModel):
    """Top-level wrapper for a standalone profile YAML file."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    version: Literal[1] = 1
    profile: ProfileEntry


__all__ = ["GlobalProfileFile"]
