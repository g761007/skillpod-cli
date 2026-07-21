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
