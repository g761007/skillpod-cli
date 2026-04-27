"""Tests for the manifest capability.

Each test corresponds to a scenario in
`openspec/changes/add-skillpod-mvp-install/specs/manifest/spec.md`.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from skillpod.manifest import (
    InstallPolicy,
    ManifestError,
    RegistrySkillsShPolicy,
    SkillEntry,
    Skillfile,
    SourceEntry,
    load,
    loads,
)

# ---- Defaults & shorthand ---------------------------------------------------


def test_minimal_manifest_applies_defaults() -> None:
    """Scenario: Minimal manifest with only `skills`."""
    text = textwrap.dedent("""
        version: 1
        skills:
          - audit
    """)
    sf = loads(text)
    assert sf.version == 1
    assert sf.registry.default == "skills.sh"
    assert sf.agents == []
    assert sf.install == InstallPolicy(mode="symlink", on_missing="error")
    assert sf.sources == []
    assert sf.skills == [SkillEntry(name="audit")]


def test_shorthand_string_entry_normalises_to_object() -> None:
    """Scenario: Shorthand string entry."""
    sf = loads("version: 1\nskills: [audit]\n")
    assert sf.skills == [SkillEntry(name="audit", source=None, version=None)]


def test_object_entry_with_explicit_source() -> None:
    """Scenario: Object entry with explicit source."""
    text = textwrap.dedent("""
        version: 1
        sources:
          - name: anthropic
            type: git
            url: https://github.com/anthropics/skills
        skills:
          - name: custom-skill
            source: anthropic
    """)
    sf = loads(text)
    assert sf.skills[0].name == "custom-skill"
    assert sf.skills[0].source == "anthropic"


def test_skill_referencing_unknown_source_is_rejected() -> None:
    text = textwrap.dedent("""
        version: 1
        skills:
          - name: custom-skill
            source: nope
    """)
    with pytest.raises(ManifestError, match="unknown source"):
        loads(text)


# ---- Strict-extra rejection -------------------------------------------------


def test_unknown_top_level_key_rejected() -> None:
    """Scenario: Unknown top-level key rejected.

    `groups:` ships in 0.3.0 — in MVP it must be flagged, not silently
    dropped.
    """
    text = textwrap.dedent("""
        version: 1
        groups:
          frontend: [audit]
        skills: []
    """)
    with pytest.raises(ManifestError, match="groups"):
        loads(text)


def test_unknown_skill_field_rejected() -> None:
    text = textwrap.dedent("""
        version: 1
        skills:
          - name: audit
            unknown_key: 1
    """)
    with pytest.raises(ManifestError, match=r"unknown_key|extra"):
        loads(text)


# ---- Agents -----------------------------------------------------------------


def test_agents_subset_accepted() -> None:
    """Scenario: Restricting fan-out to two agents (config-side)."""
    sf = loads("version: 1\nagents: [claude, codex]\nskills: []\n")
    assert sf.agents == ["claude", "codex"]


def test_unknown_agent_rejected() -> None:
    """Scenario: Unknown agent rejected."""
    with pytest.raises(ManifestError, match="unknown agent"):
        loads("version: 1\nagents: [foobar]\nskills: []\n")


def test_duplicate_agents_rejected() -> None:
    with pytest.raises(ManifestError, match="duplicates"):
        loads("version: 1\nagents: [claude, claude]\nskills: []\n")


# ---- Sources ----------------------------------------------------------------


def test_local_source_round_trip() -> None:
    text = textwrap.dedent("""
        version: 1
        sources:
          - name: local
            type: local
            path: ~/.agents/skills
            priority: 100
        skills: []
    """)
    sf = loads(text)
    assert sf.sources == [
        SourceEntry(name="local", type="local", path="~/.agents/skills", priority=100)
    ]


def test_local_source_requires_path() -> None:
    with pytest.raises(ManifestError, match="requires `path:`"):
        loads(
            textwrap.dedent("""
                version: 1
                sources:
                  - name: local
                    type: local
                skills: []
            """)
        )


def test_git_source_requires_url() -> None:
    with pytest.raises(ManifestError, match="requires `url:`"):
        loads(
            textwrap.dedent("""
                version: 1
                sources:
                  - name: anthropic
                    type: git
                skills: []
            """)
        )


def test_duplicate_source_names_rejected() -> None:
    with pytest.raises(ManifestError, match="duplicate `name`"):
        loads(
            textwrap.dedent("""
                version: 1
                sources:
                  - name: a
                    type: git
                    url: https://example.invalid/x
                  - name: a
                    type: local
                    path: /tmp
                skills: []
            """)
        )


# ---- Skill name uniqueness --------------------------------------------------


def test_duplicate_skill_names_rejected() -> None:
    with pytest.raises(ManifestError, match="duplicate `name`"):
        loads("version: 1\nskills: [audit, audit]\n")


# ---- I/O surface ------------------------------------------------------------


def test_load_reads_file(tmp_path: Path) -> None:
    p = tmp_path / "skillfile.yml"
    p.write_text("version: 1\nskills: [audit]\n", encoding="utf-8")
    sf = load(p)
    assert sf == loads("version: 1\nskills: [audit]\n")


def test_load_missing_file_errors(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="not found"):
        load(tmp_path / "nope.yml")


def test_invalid_yaml_errors() -> None:
    with pytest.raises(ManifestError, match="invalid YAML"):
        loads(":\n  - not\n: valid")


def test_empty_manifest_errors() -> None:
    with pytest.raises(ManifestError, match="empty"):
        loads("")


def test_non_mapping_top_level_errors() -> None:
    with pytest.raises(ManifestError, match="mapping"):
        loads("- nope\n")


# ---- Schema correctness sanity ---------------------------------------------


def test_skillfile_default_factory_does_not_alias() -> None:
    """Two default Skillfile instances must own independent collections."""
    a = Skillfile.model_validate({"version": 1})
    b = Skillfile.model_validate({"version": 1})
    a.agents.append("claude")
    assert b.agents == []


# ---- Trust policy (add-skillpod-trust-and-search §1) -----------------------


def test_trust_policy_defaults_when_block_omitted() -> None:
    """Scenario: Minimal manifest applies default trust-policy values.

    Corresponds to manifest spec §'Minimal manifest with only `skills`'.
    """
    sf = loads("version: 1\nskills: [audit]\n")
    assert sf.registry.skills_sh.allow_unverified is False
    assert sf.registry.skills_sh.min_installs == 0
    assert sf.registry.skills_sh.min_stars == 0


def test_trust_policy_explicit_values_round_trip() -> None:
    """Scenario: Trust policy fields round-trip through the loader.

    Corresponds to manifest spec §'Trust policy fields round-trip'.
    """
    text = textwrap.dedent("""
        version: 1
        registry:
          skills_sh:
            allow_unverified: true
            min_installs: 1000
            min_stars: 50
        skills: []
    """)
    sf = loads(text)
    assert sf.registry.skills_sh.allow_unverified is True
    assert sf.registry.skills_sh.min_installs == 1000
    assert sf.registry.skills_sh.min_stars == 50

    # Re-serialise and reload — values must survive the round-trip.
    dumped = sf.model_dump()
    sf2 = Skillfile.model_validate(dumped)
    assert sf2.registry.skills_sh.allow_unverified is True
    assert sf2.registry.skills_sh.min_installs == 1000
    assert sf2.registry.skills_sh.min_stars == 50


def test_trust_policy_non_integer_min_installs_rejected() -> None:
    """Scenario: Non-integer value for min_installs is rejected with ManifestError."""
    text = textwrap.dedent("""
        version: 1
        registry:
          skills_sh:
            min_installs: "lots"
        skills: []
    """)
    with pytest.raises(ManifestError):
        loads(text)


def test_trust_policy_non_integer_min_stars_rejected() -> None:
    """Scenario: Non-integer value for min_stars is rejected with ManifestError."""
    text = textwrap.dedent("""
        version: 1
        registry:
          skills_sh:
            min_stars: "many"
        skills: []
    """)
    with pytest.raises(ManifestError):
        loads(text)


def test_trust_policy_non_bool_allow_unverified_rejected() -> None:
    """Scenario: Non-boolean value for allow_unverified is rejected with ManifestError."""
    text = textwrap.dedent("""
        version: 1
        registry:
          skills_sh:
            allow_unverified: "yes"
        skills: []
    """)
    with pytest.raises(ManifestError):
        loads(text)


def test_trust_policy_unknown_key_rejected() -> None:
    """Unknown keys inside `registry.skills_sh` must be rejected (extra=forbid)."""
    text = textwrap.dedent("""
        version: 1
        registry:
          skills_sh:
            allow_unverified: false
            typo_key: 1
        skills: []
    """)
    with pytest.raises(ManifestError):
        loads(text)


def test_registry_skills_sh_policy_model_standalone() -> None:
    """RegistrySkillsShPolicy is constructable standalone with expected defaults."""
    policy = RegistrySkillsShPolicy()
    assert policy.allow_unverified is False
    assert policy.min_installs == 0
    assert policy.min_stars == 0
