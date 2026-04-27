"""Manifest capability: skillfile.yml schema + loader."""

from skillpod.manifest.loader import ManifestError, load, loads
from skillpod.manifest.models import (
    SUPPORTED_AGENTS,
    AgentEntry,
    InstallPolicy,
    RegistryConfig,
    RegistrySkillsShPolicy,
    SkillEntry,
    Skillfile,
    SkillRef,
    SourceEntry,
)

__all__ = [
    "SUPPORTED_AGENTS",
    "AgentEntry",
    "InstallPolicy",
    "ManifestError",
    "RegistryConfig",
    "RegistrySkillsShPolicy",
    "SkillEntry",
    "SkillRef",
    "Skillfile",
    "SourceEntry",
    "load",
    "loads",
]
