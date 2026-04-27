"""Manifest capability: skillfile.yml schema + loader."""

from skillpod.manifest.loader import ManifestError, load, loads
from skillpod.manifest.models import (
    SUPPORTED_AGENTS,
    InstallPolicy,
    RegistryConfig,
    RegistrySkillsShPolicy,
    SkillEntry,
    Skillfile,
    SourceEntry,
)

__all__ = [
    "SUPPORTED_AGENTS",
    "InstallPolicy",
    "ManifestError",
    "RegistryConfig",
    "RegistrySkillsShPolicy",
    "SkillEntry",
    "Skillfile",
    "SourceEntry",
    "load",
    "loads",
]
