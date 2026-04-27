"""Discover project-local user skills under .skillpod/user_skills."""

from __future__ import annotations

from pathlib import Path

from skillpod.sources.types import ResolvedSkill

USER_SKILLS_DIR = ".skillpod/user_skills"


def user_skills_root(project_root: Path) -> Path:
    return Path(project_root).resolve() / USER_SKILLS_DIR


def discover_user_skills(project_root: Path) -> dict[str, Path]:
    """Return immediate child directories as ``{skill_name: absolute_path}``."""

    root = user_skills_root(project_root)
    if not root.exists():
        return {}
    if not root.is_dir():
        return {}

    discovered: dict[str, Path] = {}
    for child in sorted(root.iterdir(), key=lambda p: p.name):
        if child.is_dir():
            discovered[child.name] = child.resolve()
    return discovered


def resolve_user_skill(name: str, path: Path) -> ResolvedSkill:
    return ResolvedSkill(
        name=name,
        source_kind="local",
        source_name=None,
        path=path.resolve(),
        url=None,
        commit=None,
    )


__all__ = ["USER_SKILLS_DIR", "discover_user_skills", "resolve_user_skill", "user_skills_root"]
