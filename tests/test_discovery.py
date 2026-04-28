"""Unit tests for `skillpod.sources.discovery.discover_skills`."""

from __future__ import annotations

import textwrap
from pathlib import Path

from skillpod.sources.discovery import discover_skills


def _write_skill(parent: Path, name: str, *, description: str | None = None) -> None:
    skill = parent / name
    skill.mkdir(parents=True)
    if description is None:
        body = f"# {name}\n"
    else:
        body = textwrap.dedent(
            f"""\
            ---
            name: {name}
            description: {description}
            ---

            # {name}
            """
        )
    (skill / "SKILL.md").write_text(body, encoding="utf-8")


def test_discover_root_level_skills(tmp_path: Path) -> None:
    _write_skill(tmp_path, "audit", description="Audit a project")
    _write_skill(tmp_path, "polish", description="Polish a draft")

    discovered = discover_skills(tmp_path)

    assert [s.name for s in discovered] == ["audit", "polish"]
    descs = {s.name: s.description for s in discovered}
    assert descs == {"audit": "Audit a project", "polish": "Polish a draft"}


def test_discover_handles_missing_frontmatter(tmp_path: Path) -> None:
    _write_skill(tmp_path, "plain")  # no frontmatter

    discovered = discover_skills(tmp_path)

    assert len(discovered) == 1
    assert discovered[0].name == "plain"
    assert discovered[0].description == ""


def test_discover_treats_root_as_single_skill(tmp_path: Path) -> None:
    (tmp_path / "SKILL.md").write_text(
        textwrap.dedent(
            """\
            ---
            description: Top-level
            ---

            # root
            """
        ),
        encoding="utf-8",
    )

    discovered = discover_skills(tmp_path)

    assert len(discovered) == 1
    assert discovered[0].name == tmp_path.name
    assert discovered[0].rel_path == "."
    assert discovered[0].description == "Top-level"


def test_discover_skips_hidden_and_excluded(tmp_path: Path) -> None:
    _write_skill(tmp_path, "real")
    # These should be ignored:
    _write_skill(tmp_path, ".hidden")
    _write_skill(tmp_path, "node_modules")
    _write_skill(tmp_path, "dist")
    _write_skill(tmp_path, ".git")

    discovered = discover_skills(tmp_path)
    assert [s.name for s in discovered] == ["real"]


def test_discover_finds_nested_skills_within_max_depth(tmp_path: Path) -> None:
    _write_skill(tmp_path / "skills", "a")
    _write_skill(tmp_path / "skills", "b")

    discovered = discover_skills(tmp_path)
    names = sorted(s.name for s in discovered)
    assert names == ["a", "b"]
    rel_paths = {s.name: s.rel_path for s in discovered}
    assert rel_paths["a"].endswith("a")


def test_discover_ignores_too_deep(tmp_path: Path) -> None:
    too_deep = tmp_path / "a" / "b" / "c"
    _write_skill(too_deep, "deep")

    discovered = discover_skills(tmp_path)
    assert discovered == []


def test_discover_tolerates_bad_frontmatter(tmp_path: Path) -> None:
    skill = tmp_path / "broken"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nthis is: : not: valid: yaml\n---\n# broken\n",
        encoding="utf-8",
    )

    discovered = discover_skills(tmp_path)
    assert len(discovered) == 1
    assert discovered[0].name == "broken"
    assert discovered[0].description == ""


def test_discover_returns_empty_for_nonexistent_root(tmp_path: Path) -> None:
    assert discover_skills(tmp_path / "does-not-exist") == []
