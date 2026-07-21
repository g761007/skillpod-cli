"""Guards for mistakes that only show up on a platform CI runs but nobody develops on."""

from __future__ import annotations

import re
from pathlib import Path

TESTS_DIR = Path(__file__).parent

# `f"file://{path}"` yields `file:///tmp/x` on POSIX — valid — but
# `file://C:\Users\x` on Windows, which git rejects. The bug is therefore
# invisible to everyone developing on macOS or Linux and only ever surfaces as
# a Windows CI failure, one round-trip later.
_HAND_BUILT_FILE_URL = re.compile(r"""["']file://\{|["']file://["']\s*\+""")


def test_no_test_hand_builds_a_file_url() -> None:
    """Use `Path.as_uri()`, which is correct on every platform.

    This guard exists because the mistake was made, fixed, written up in a
    commit message, and then made again in the next pull request. A rule that
    runs in CI is worth more than an intention to remember.
    """
    offenders: list[str] = []
    for path in sorted(TESTS_DIR.glob("*.py")):
        if path.name == Path(__file__).name:
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if _HAND_BUILT_FILE_URL.search(line):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")

    assert not offenders, (
        "build file:// URLs with Path.as_uri(), not string interpolation "
        "(it produces file://C:\\... on Windows):\n  " + "\n  ".join(offenders)
    )


# `Path.home()` goes through `ntpath.expanduser` on Windows, which reads
# `USERPROFILE` and never looks at `HOME`. Setting `HOME` alone redirects the
# home directory on POSIX and does nothing at all on Windows.
_BARE_HOME_SETENV = re.compile(r"""setenv\(\s*["'](HOME|USERPROFILE)["']""")


def test_no_test_sets_home_without_userprofile() -> None:
    """Redirect the home directory with `set_home`, which sets both variables.

    Setting only `HOME` is not a partial fix — on Windows it is no fix. The
    home stays wherever it was, so the code under test reads one directory
    while the test populates another, and all 34 Windows failures in issue #10
    reported the feature as broken rather than the isolation as inert.
    """
    allowed = {"_env.py", Path(__file__).name}
    offenders: list[str] = []
    for path in sorted(TESTS_DIR.glob("*.py")):
        if path.name in allowed:
            continue
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if _BARE_HOME_SETENV.search(line):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")

    assert not offenders, (
        "set the home directory with tests._env.set_home(monkeypatch, path) — "
        "setting HOME alone is silently inert on Windows:\n  "
        + "\n  ".join(offenders)
    )
