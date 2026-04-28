"""Tests for the source-mode of `skillpod add` (vercel-labs/skills style)."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from skillpod.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setenv("SKILLPOD_CACHE_DIR", str(cache))


def _make_local_skill_pool(parent: Path, *, names: list[str]) -> Path:
    pool = parent / "pool"
    pool.mkdir()
    for name in names:
        skill = pool / name
        skill.mkdir()
        (skill / "SKILL.md").write_text(
            textwrap.dedent(
                f"""\
                ---
                description: Local skill {name}
                ---

                # {name}
                """
            ),
            encoding="utf-8",
        )
    return pool


def _make_project(parent: Path, *, agents: str = "[claude]") -> Path:
    proj = parent / "project"
    proj.mkdir()
    (proj / "skillfile.yml").write_text(
        textwrap.dedent(f"""\
            version: 1
            agents: {agents}
            skills: []
        """),
        encoding="utf-8",
    )
    return proj


# ---- bare-name back-compat (sanity) ----------------------------------------


def test_bare_name_rejects_source_only_flags(
    runner: CliRunner, tmp_path: Path
) -> None:
    proj = _make_project(tmp_path)
    result = runner.invoke(
        app,
        ["add", "audit", "-s", "x", "--manifest", str(proj / "skillfile.yml")],
    )
    assert result.exit_code != 0
    combined = (result.stdout + (result.stderr or "")).lower()
    assert "require a source" in combined


def test_bare_name_legacy_path_still_works_for_local_source(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Sanity: the existing behaviour is preserved when positional is bare."""
    pool = tmp_path / "pool"
    (pool / "audit").mkdir(parents=True)
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "skillfile.yml").write_text(
        textwrap.dedent(f"""\
            version: 1
            agents: [claude]
            sources:
              - name: local
                type: local
                path: {pool}
            skills: []
        """),
        encoding="utf-8",
    )
    result = runner.invoke(
        app, ["add", "audit", "--manifest", str(proj / "skillfile.yml")]
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert (proj / ".claude" / "skills" / "audit").exists()


# ---- source-mode listing (-l) ---------------------------------------------


def test_list_local_source_human(runner: CliRunner, tmp_path: Path) -> None:
    pool = _make_local_skill_pool(tmp_path, names=["pdf", "docx"])
    proj = _make_project(tmp_path)
    result = runner.invoke(
        app,
        [
            "add",
            str(pool),
            "-l",
            "--manifest",
            str(proj / "skillfile.yml"),
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert "pdf" in result.stdout
    assert "docx" in result.stdout
    assert "Local skill pdf" in result.stdout


def test_list_local_source_json(runner: CliRunner, tmp_path: Path) -> None:
    pool = _make_local_skill_pool(tmp_path, names=["pdf"])
    proj = _make_project(tmp_path)
    result = runner.invoke(
        app,
        [
            "add",
            str(pool),
            "-l",
            "--json",
            "--manifest",
            str(proj / "skillfile.yml"),
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["source"]["kind"] == "local"
    assert [s["name"] for s in payload["skills"]] == ["pdf"]
    assert payload["skills"][0]["description"] == "Local skill pdf"


# ---- source-mode project install ------------------------------------------


def test_source_mode_adds_source_and_installs_selected(
    runner: CliRunner, tmp_path: Path
) -> None:
    pool = _make_local_skill_pool(tmp_path, names=["pdf", "docx", "xlsx"])
    proj = _make_project(tmp_path)
    result = runner.invoke(
        app,
        [
            "add",
            str(pool),
            "-s",
            "pdf",
            "-s",
            "docx",
            "-y",
            "--manifest",
            str(proj / "skillfile.yml"),
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")

    manifest = (proj / "skillfile.yml").read_text(encoding="utf-8")
    # Source auto-added under the derived name (pool dir basename)
    assert "type: local" in manifest
    assert str(pool) in manifest
    # Both selected skills present, xlsx omitted
    assert "name: pdf" in manifest
    assert "name: docx" in manifest
    assert "xlsx" not in manifest

    assert (proj / ".skillpod" / "skills" / "pdf").is_symlink()
    assert (proj / ".skillpod" / "skills" / "docx").is_symlink()
    assert (proj / ".claude" / "skills" / "pdf").exists()
    assert (proj / ".claude" / "skills" / "docx").exists()


def test_source_mode_star_installs_all(
    runner: CliRunner, tmp_path: Path
) -> None:
    pool = _make_local_skill_pool(tmp_path, names=["a", "b", "c"])
    proj = _make_project(tmp_path)
    result = runner.invoke(
        app,
        [
            "add",
            str(pool),
            "-s",
            "*",
            "-y",
            "--manifest",
            str(proj / "skillfile.yml"),
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    for name in ("a", "b", "c"):
        assert (proj / ".claude" / "skills" / name).exists()


def test_source_mode_unknown_skill_errors(
    runner: CliRunner, tmp_path: Path
) -> None:
    pool = _make_local_skill_pool(tmp_path, names=["pdf"])
    proj = _make_project(tmp_path)
    snapshot = (proj / "skillfile.yml").read_text(encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "add",
            str(pool),
            "-s",
            "ghost",
            "-y",
            "--manifest",
            str(proj / "skillfile.yml"),
        ],
    )
    assert result.exit_code != 0
    # Manifest unchanged on rejection.
    assert (proj / "skillfile.yml").read_text(encoding="utf-8") == snapshot


def test_source_mode_rolls_back_on_install_failure(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Selected skill discoverable but materialisation fails (missing dir)."""
    pool = tmp_path / "pool"
    pool.mkdir()
    skill = pool / "pdf"
    skill.mkdir()
    (skill / "SKILL.md").write_text("# pdf\n", encoding="utf-8")
    proj = _make_project(tmp_path)
    snapshot = (proj / "skillfile.yml").read_text(encoding="utf-8")

    # Trigger failure by passing an unknown agent flag (validated post-snapshot).
    result = runner.invoke(
        app,
        [
            "add",
            str(pool),
            "-s",
            "pdf",
            "-a",
            "codex",  # not in declared agents [claude]
            "-y",
            "--manifest",
            str(proj / "skillfile.yml"),
        ],
    )
    assert result.exit_code != 0
    assert (proj / "skillfile.yml").read_text(encoding="utf-8") == snapshot


def test_source_mode_dedupe_existing_source_entry(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Re-adding from the same source reuses the existing entry."""
    pool = _make_local_skill_pool(tmp_path, names=["pdf", "docx"])
    proj = _make_project(tmp_path)

    first = runner.invoke(
        app,
        [
            "add",
            str(pool),
            "-s",
            "pdf",
            "-y",
            "--manifest",
            str(proj / "skillfile.yml"),
        ],
    )
    assert first.exit_code == 0, first.stdout + (first.stderr or "")
    assert (proj / "skillfile.yml").read_text(encoding="utf-8").count("type: local") == 1

    second = runner.invoke(
        app,
        [
            "add",
            str(pool),
            "-s",
            "docx",
            "-y",
            "--manifest",
            str(proj / "skillfile.yml"),
        ],
    )
    assert second.exit_code == 0, second.stdout + (second.stderr or "")
    final = (proj / "skillfile.yml").read_text(encoding="utf-8")
    assert final.count("type: local") == 1  # still only one source entry
    assert "name: pdf" in final
    assert "name: docx" in final


def test_source_mode_skipped_already_in_manifest(
    runner: CliRunner, tmp_path: Path
) -> None:
    pool = _make_local_skill_pool(tmp_path, names=["pdf", "docx"])
    proj = _make_project(tmp_path)

    runner.invoke(
        app,
        ["add", str(pool), "-s", "pdf", "-y", "--manifest", str(proj / "skillfile.yml")],
    )
    result = runner.invoke(
        app,
        [
            "add",
            str(pool),
            "-s",
            "pdf",
            "-s",
            "docx",
            "-y",
            "--json",
            "--manifest",
            str(proj / "skillfile.yml"),
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "pdf" in payload["skipped"]
    assert "docx" in payload["added"]


def test_source_mode_agent_filter_restricts_fanout(
    runner: CliRunner, tmp_path: Path
) -> None:
    pool = _make_local_skill_pool(tmp_path, names=["pdf"])
    proj = _make_project(tmp_path, agents="[claude, codex]")
    result = runner.invoke(
        app,
        [
            "add",
            str(pool),
            "-s",
            "pdf",
            "-a",
            "claude",
            "-y",
            "--manifest",
            str(proj / "skillfile.yml"),
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert (proj / ".claude" / "skills" / "pdf").exists()
    # codex was declared in manifest but excluded by -a — should not exist yet.
    assert not (proj / ".codex" / "skills" / "pdf").exists()
    # Manifest's agents list is unchanged (no narrowing was persisted).
    manifest_text = (proj / "skillfile.yml").read_text(encoding="utf-8")
    assert "codex" in manifest_text


# ---- source-mode global install (-g) --------------------------------------


def test_source_mode_global_installs_with_fanout(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    pool = _make_local_skill_pool(tmp_path, names=["pdf"])
    result = runner.invoke(
        app,
        [
            "add",
            str(pool),
            "-s",
            "pdf",
            "-g",
            "-a",
            "claude",
            "-y",
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert (fake_home / ".skillpod" / "skills" / "pdf").is_symlink()
    assert (fake_home / ".claude" / "skills" / "pdf").exists()
    # codex was not requested → no fan-out there.
    assert not (fake_home / ".codex" / "skills" / "pdf").exists()


def test_source_mode_global_default_fans_out_to_all_known_agents(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    pool = _make_local_skill_pool(tmp_path, names=["pdf"])
    result = runner.invoke(
        app,
        ["add", str(pool), "-s", "pdf", "-g", "-y"],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    for agent in ("claude", "codex", "gemini", "cursor", "opencode", "antigravity"):
        assert (fake_home / f".{agent}" / "skills" / "pdf").exists(), agent


def test_source_mode_global_unknown_agent_errors(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    pool = _make_local_skill_pool(tmp_path, names=["pdf"])
    result = runner.invoke(
        app,
        ["add", str(pool), "-s", "pdf", "-g", "-a", "nope", "-y"],
    )
    assert result.exit_code == 1
    combined = (result.stdout + (result.stderr or "")).lower()
    assert "unknown agent" in combined or "supported" in combined
