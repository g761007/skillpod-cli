"""Layer origin enum for effective skill provenance tracking."""

from __future__ import annotations

from enum import StrEnum


class LayerOrigin(StrEnum):
    PROJECT = "project"
    USER_SKILL = "user_skill"
    PROFILE_FILTER = "profile_filter"
    GLOBAL_PROFILE_FILTER = "global_profile_filter"
    POLICY_BLOCKED_GLOBAL = "policy_blocked_global"


__all__ = ["LayerOrigin"]
