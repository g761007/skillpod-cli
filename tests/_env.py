"""Environment helpers shared by the test suite."""

from __future__ import annotations

from pathlib import Path

import pytest


def set_home(monkeypatch: pytest.MonkeyPatch, path: Path | str) -> Path:
    """Point the home directory at ``path`` on every platform.

    ``Path.home()`` resolves through ``ntpath.expanduser`` on Windows, which
    reads ``USERPROFILE`` and never consults ``HOME``. Setting only ``HOME`` —
    the obvious spelling, and the one this suite used for 63 call sites — is
    therefore silently inert there: the code under test keeps reading whichever
    home was set last, while the test writes its fixtures somewhere else. Every
    assertion then fails as "not found", pointing at the feature rather than at
    the isolation that quietly did nothing.

    Both variables are set together so the two platforms cannot disagree.
    Enforced by ``test_conventions.py``, because remembering to set the second
    one is exactly the kind of thing that does not survive the next test.
    """
    monkeypatch.setenv("HOME", str(path))
    monkeypatch.setenv("USERPROFILE", str(path))
    return Path(path)


__all__ = ["set_home"]
