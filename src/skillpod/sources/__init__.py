"""Source-resolver capability: local + git resolution, immutable cache."""

from skillpod.sources.cache import cache_path_for, cache_root, parse_repo_url
from skillpod.sources.errors import GitOperationError, SourceError, SourceNotFound
from skillpod.sources.git import (
    populate_cache,
    resolve_default_branch,
    resolve_git,
    resolve_ref,
)
from skillpod.sources.local import resolve_local
from skillpod.sources.resolver import resolve_from_sources
from skillpod.sources.types import ResolvedSkill

__all__ = [
    "GitOperationError",
    "ResolvedSkill",
    "SourceError",
    "SourceNotFound",
    "cache_path_for",
    "cache_root",
    "parse_repo_url",
    "populate_cache",
    "resolve_default_branch",
    "resolve_from_sources",
    "resolve_git",
    "resolve_local",
    "resolve_ref",
]
