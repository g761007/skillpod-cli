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

    pdf_root = proj / ".skillpod" / "skills" / "pdf"
    docx_root = proj / ".skillpod" / "skills" / "docx"
    assert pdf_root.is_dir() and not pdf_root.is_symlink()
    assert docx_root.is_dir() and not docx_root.is_symlink()
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


def test_source_mode_global_installs_without_fanout(
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
            "-y",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    payload = json.loads(result.stdout)
    assert payload["skills"][0]["fanned_out_to"] == []
    global_root = fake_home / ".skillpod" / "skills" / "pdf"
    assert global_root.is_dir() and not global_root.is_symlink()
    assert not (fake_home / ".claude" / "skills" / "pdf").exists()
    assert not (fake_home / ".codex" / "skills" / "pdf").exists()


def test_source_mode_global_default_does_not_fanout(
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
    assert (fake_home / ".skillpod" / "skills" / "pdf").is_dir()
    for agent in ("claude", "codex", "gemini", "cursor", "opencode", "antigravity"):
        assert not (fake_home / f".{agent}" / "skills" / "pdf").exists(), agent


def test_source_mode_global_rejects_agent_flag(
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
        ["add", str(pool), "-s", "pdf", "-g", "-a", "claude", "-y"],
    )
    assert result.exit_code == 1
    combined = (result.stdout + (result.stderr or "")).lower()
    assert "no longer links" in combined or "fans out" in combined
    assert not (fake_home / ".skillpod" / "skills" / "pdf").exists()


# ---- Install-root durability (cache-prune resistance) ---------------------


def test_global_install_survives_cache_prune(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``~/.skillpod/skills/<name>`` must remain readable after the
    download cache is wiped. Regression for the global symlink-into-cache
    bug — install root is now a real-directory copy."""
    import shutil as _shutil

    from tests._git_fixtures import make_skill_repo

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    repo_path, _sha = make_skill_repo(
        tmp_path / "git-side",
        skill_name="audit",
        skill_files={
            "SKILL.md": (
                "---\n"
                "description: audit skill\n"
                "---\n\n"
                "# audit\n"
            ),
        },
    )
    result = runner.invoke(
        app,
        [
            "add",
            str(repo_path),
            "-s",
            "audit",
            "-g",
            "-y",
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")

    install_root_dir = fake_home / ".skillpod" / "skills" / "audit"
    skill_md = install_root_dir / "SKILL.md"
    assert install_root_dir.is_dir()
    assert not install_root_dir.is_symlink()
    assert "# audit" in skill_md.read_text(encoding="utf-8")

    # Wipe the entire skillpod download cache.
    import os
    cache_dir = Path(os.environ["SKILLPOD_CACHE_DIR"])
    _shutil.rmtree(cache_dir)

    # Install root still resolves to real content.
    assert install_root_dir.is_dir()
    assert "# audit" in skill_md.read_text(encoding="utf-8")


# ---- Default-branch auto-detection ----------------------------------------


def test_source_mode_auto_detects_master_default_branch(
    runner: CliRunner, tmp_path: Path
) -> None:
    """`skillpod add owner/repo` (no --ref) must succeed even when the
    repository's default branch is `master`. Regression for the hardcoded
    ``ref="main"`` default that broke `git ls-remote --exit-code <url> main`
    on master-default repos like ``alchaincyf/huashu-design``."""
    from tests._git_fixtures import make_root_skill_repo

    repo_path, _sha = make_root_skill_repo(
        tmp_path / "git-side", repo_name="huashu-design", branch="master"
    )
    proj = _make_project(tmp_path)

    result = runner.invoke(
        app,
        [
            "add",
            f"file://{repo_path}",
            "-y",
            "--manifest",
            str(proj / "skillfile.yml"),
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")

    # The resolved branch name (master) is written back into the manifest.
    manifest_text = (proj / "skillfile.yml").read_text(encoding="utf-8")
    assert "ref: master" in manifest_text
    assert (proj / ".skillpod" / "skills" / "huashu-design" / "SKILL.md").is_file()


def test_source_mode_explicit_ref_is_respected(
    runner: CliRunner, tmp_path: Path
) -> None:
    """An explicit ``--ref`` always wins over the auto-detect behaviour."""
    from tests._git_fixtures import make_root_skill_repo

    repo_path, _sha = make_root_skill_repo(
        tmp_path / "git-side", repo_name="pinned", branch="develop"
    )
    proj = _make_project(tmp_path)

    result = runner.invoke(
        app,
        [
            "add",
            f"file://{repo_path}",
            "--ref",
            "develop",
            "-y",
            "--manifest",
            str(proj / "skillfile.yml"),
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert "ref: develop" in (proj / "skillfile.yml").read_text(encoding="utf-8")


# ---- Root-is-skill (single-skill repo) -----------------------------------


def test_source_mode_root_is_skill_installs_under_derived_name(
    runner: CliRunner, tmp_path: Path
) -> None:
    """`skillpod add <git source>` for a repo whose root *is* the skill
    auto-installs a single skill named after the URL's derived name (e.g.
    ``vibe`` from ``file:///.../vibe``), not the cache directory basename."""
    from tests._git_fixtures import make_root_skill_repo

    repo_path, _sha = make_root_skill_repo(tmp_path / "git-side", repo_name="vibe")
    proj = _make_project(tmp_path)

    result = runner.invoke(
        app,
        [
            "add",
            f"file://{repo_path}",
            "-y",
            "--manifest",
            str(proj / "skillfile.yml"),
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")

    install_root_dir = proj / ".skillpod" / "skills" / "vibe"
    assert install_root_dir.is_dir() and not install_root_dir.is_symlink()
    assert (install_root_dir / "SKILL.md").is_file()
    assert (proj / ".claude" / "skills" / "vibe").exists()

    manifest_text = (proj / "skillfile.yml").read_text(encoding="utf-8")
    assert "name: vibe" in manifest_text
    assert "type: git" in manifest_text
    assert f"file://{repo_path}" in manifest_text


def test_source_mode_root_is_skill_global_uses_derived_name(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Global mode for a root-is-skill git source materialises under the
    derived name (no commit SHA leaking from the cache layout)."""
    from tests._git_fixtures import make_root_skill_repo

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    repo_path, _sha = make_root_skill_repo(tmp_path / "git-side", repo_name="vibe")

    result = runner.invoke(
        app,
        [
            "add",
            f"file://{repo_path}",
            "-g",
            "-y",
        ],
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")

    install_root_dir = fake_home / ".skillpod" / "skills" / "vibe"
    assert install_root_dir.is_dir() and not install_root_dir.is_symlink()
    assert (install_root_dir / "SKILL.md").is_file()
    assert not (fake_home / ".claude" / "skills" / "vibe").exists()


def test_source_mode_root_is_skill_reinstall_via_install_succeeds(
    runner: CliRunner, tmp_path: Path
) -> None:
    """After `add`, a follow-up `install` (which goes through the resolver
    again with the manifest's logical skill name) must still resolve the
    root-is-skill via the resolver fallback rather than re-failing."""
    from tests._git_fixtures import make_root_skill_repo

    repo_path, _sha = make_root_skill_repo(tmp_path / "git-side", repo_name="vibe")
    proj = _make_project(tmp_path)

    add_result = runner.invoke(
        app,
        [
            "add",
            f"file://{repo_path}",
            "-y",
            "--manifest",
            str(proj / "skillfile.yml"),
        ],
    )
    assert add_result.exit_code == 0, add_result.stdout + (add_result.stderr or "")

    install_result = runner.invoke(
        app,
        ["install", "--manifest", str(proj / "skillfile.yml")],
    )
    assert install_result.exit_code == 0, install_result.stdout + (
        install_result.stderr or ""
    )
    assert (proj / ".skillpod" / "skills" / "vibe" / "SKILL.md").is_file()


def test_global_install_idempotent_when_content_matches(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-running ``skillpod add -g`` with the same source content must
    succeed without ``--force`` (hash-based idempotency)."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    pool = _make_local_skill_pool(tmp_path, names=["pdf"])
    args = ["add", str(pool), "-s", "pdf", "-g", "-y"]
    first = runner.invoke(app, args)
    assert first.exit_code == 0, first.stdout + (first.stderr or "")

    install_root_dir = fake_home / ".skillpod" / "skills" / "pdf"
    manifest = install_root_dir / "SKILL.md"
    mtime_before = manifest.stat().st_mtime_ns

    second = runner.invoke(app, args)
    assert second.exit_code == 0, second.stdout + (second.stderr or "")
    # Idempotent skip: file untouched on second run.
    assert manifest.stat().st_mtime_ns == mtime_before
