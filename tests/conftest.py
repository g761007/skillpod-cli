"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests._env import set_home


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Give every test its own home directory.

    skillpod reads `~/.skillpod/` for the global skill set and install record,
    and since `install.prefer_global` landed the *project* pipeline consults it
    too. Without isolation, a test that installs a skill named `audit` would
    silently skip the install on any machine whose owner happens to have
    `audit` installed globally — a suite that passes or fails depending on
    whose laptop it runs on. That dependency was always latent; prefer_global
    is what made it bite.

    `USERPROFILE` is set alongside `HOME` because `Path.home()` resolves via
    `ntpath.expanduser` on Windows, which reads `USERPROFILE` and ignores
    `HOME`. Setting only `HOME` would leave the isolation silently inert there.

    Tests needing a specific home can still set it themselves or pass `home=`
    explicitly; both take effect after this fixture.
    """
    home = tmp_path / "_home"
    home.mkdir(exist_ok=True)
    set_home(monkeypatch, home)
    return home
