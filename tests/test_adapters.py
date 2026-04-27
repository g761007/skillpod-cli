"""Tests for the adapter interface, IdentityAdapter, and adapter registry.

Scenarios trace to
``openspec/changes/add-skillpod-adapter-layer/specs/installer/spec.md``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from skillpod.installer.adapter import InstallMode
from skillpod.installer.adapter_default import IdentityAdapter
from skillpod.installer.adapter_registry import get_adapter, register_adapter, reset_registry
from skillpod.manifest.models import SUPPORTED_AGENTS


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    """Restore the default registry after every test."""
    reset_registry()
    yield  # type: ignore[misc]
    reset_registry()


# ---- IdentityAdapter: SYMLINK -----------------------------------------------


def test_identity_adapter_symlink_creates_symlink(tmp_path: Path) -> None:
    """IdentityAdapter SYMLINK: target is a symbolic link to source_dir."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "manifest.md").write_text("# skill", encoding="utf-8")
    target = tmp_path / "target"

    IdentityAdapter().adapt(
        skill_name="audit",
        source_dir=source,
        target_dir=target,
        mode=InstallMode.SYMLINK,
    )

    assert target.is_symlink()
    assert target.resolve() == source.resolve()
    assert (target / "manifest.md").read_text(encoding="utf-8") == "# skill"


# ---- IdentityAdapter: COPY --------------------------------------------------


def test_identity_adapter_copy_creates_independent_tree(tmp_path: Path) -> None:
    """IdentityAdapter COPY: creates an independent recursive copy.

    Modifying a file in the copy must NOT affect the source.
    """
    source = tmp_path / "source"
    source.mkdir()
    (source / "manifest.md").write_text("original", encoding="utf-8")
    (source / "sub").mkdir()
    (source / "sub" / "deep.txt").write_text("deep", encoding="utf-8")
    target = tmp_path / "target"

    IdentityAdapter().adapt(
        skill_name="audit",
        source_dir=source,
        target_dir=target,
        mode=InstallMode.COPY,
    )

    assert target.is_dir()
    assert not target.is_symlink()
    assert (target / "manifest.md").read_text(encoding="utf-8") == "original"
    assert (target / "sub" / "deep.txt").read_text(encoding="utf-8") == "deep"

    # Modifying the copy must not affect the source.
    (target / "manifest.md").write_text("modified", encoding="utf-8")
    assert (source / "manifest.md").read_text(encoding="utf-8") == "original"


# ---- IdentityAdapter: HARDLINK ----------------------------------------------


def test_identity_adapter_hardlink_shares_inodes(tmp_path: Path) -> None:
    """IdentityAdapter HARDLINK: each file shares an inode with its source.

    Skipped when source and target are on different filesystems (CI may mount
    tmp separately).
    """
    source = tmp_path / "source"
    source.mkdir()
    (source / "manifest.md").write_text("# skill", encoding="utf-8")
    (source / "sub").mkdir()
    (source / "sub" / "deep.txt").write_text("deep", encoding="utf-8")
    target = tmp_path / "target"

    # Skip if cross-device (hardlinks impossible).
    src_dev = os.stat(source).st_dev
    dst_dev = os.stat(tmp_path).st_dev
    if src_dev != dst_dev:
        pytest.skip("source and target on different devices — hardlink not possible")

    IdentityAdapter().adapt(
        skill_name="audit",
        source_dir=source,
        target_dir=target,
        mode=InstallMode.HARDLINK,
    )

    assert target.is_dir()
    assert not target.is_symlink()

    src_ino = os.stat(source / "manifest.md").st_ino
    dst_ino = os.stat(target / "manifest.md").st_ino
    assert src_ino == dst_ino, "hardlinked files must share the same inode"

    src_deep_ino = os.stat(source / "sub" / "deep.txt").st_ino
    dst_deep_ino = os.stat(target / "sub" / "deep.txt").st_ino
    assert src_deep_ino == dst_deep_ino


# ---- Adapter registry -------------------------------------------------------


def test_registry_default_returns_identity_adapter_for_every_supported_agent() -> None:
    """Default registry maps every supported agent to IdentityAdapter."""
    for agent in SUPPORTED_AGENTS:
        adapter = get_adapter(agent)
        assert isinstance(adapter, IdentityAdapter), (
            f"expected IdentityAdapter for {agent!r}, got {type(adapter).__name__}"
        )


def test_registry_register_overrides_default() -> None:
    """register_adapter replaces the default for the given agent."""

    class CustomAdapter:
        def adapt(self, *, skill_name, source_dir, target_dir, mode):
            pass

    custom = CustomAdapter()
    register_adapter("claude", custom)
    assert get_adapter("claude") is custom


def test_registry_reset_restores_defaults() -> None:
    """reset_registry restores IdentityAdapter for every agent."""

    class Stub:
        def adapt(self, **_):
            pass

    register_adapter("claude", Stub())
    reset_registry()
    assert isinstance(get_adapter("claude"), IdentityAdapter)


def test_registry_unknown_agent_falls_back_to_identity() -> None:
    """get_adapter returns IdentityAdapter for an unregistered agent name."""
    adapter = get_adapter("totally-unknown-agent-xyz")
    assert isinstance(adapter, IdentityAdapter)


def test_identity_adapter_modes_supported_property() -> None:
    """IdentityAdapter.modes_supported returns the expected string."""
    adapter = IdentityAdapter()
    assert adapter.modes_supported == "symlink, copy, hardlink"
