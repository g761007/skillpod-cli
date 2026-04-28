"""End-to-end CLI tests via Typer's CliRunner.

Scenarios trace to
`openspec/changes/add-skillpod-mvp-install/specs/cli/spec.md`.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from typer.testing import CliRunner

from skillpod.cli import app
from tests._git_fixtures import make_skill_repo

_REGISTRY_BASE = "https://registry.test"


@pytest.fixture
def runner() -> CliRunner:
    # mix_stderr=False so stderr lands separately and we can probe it.
    return CliRunner()


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setenv("SKILLPOD_CACHE_DIR", str(cache))
    monkeypatch.setenv("SKILLPOD_REGISTRY_URL", _REGISTRY_BASE)


def _project(tmp_path: Path, manifest: str) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "skillfile.yml").write_text(manifest, encoding="utf-8")
    return proj


# ---- init -------------------------------------------------------------------


def test_init_fresh_creates_manifest_and_gitignore(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario: Fresh init."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0, result.stdout

    manifest = (tmp_path / "skillfile.yml").read_text(encoding="utf-8")
    assert "version: 1" in manifest
    assert "skills: []" in manifest

    gitignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".skillpod/" in gitignore


def test_init_does_not_overwrite_existing_manifest(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario: Re-running `init` is safe."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "skillfile.yml").write_text("# user content\n", encoding="utf-8")
    result = runner.invoke(app, ["init"])
    assert result.exit_code != 0
    # The original content stays intact.
    assert (tmp_path / "skillfile.yml").read_text(encoding="utf-8") == "# user content\n"


def test_init_does_not_duplicate_gitignore_entry(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gitignore").write_text(".skillpod/\n", encoding="utf-8")
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert text.count(".skillpod/") == 1


# ---- install + lockfile -----------------------------------------------------


def test_install_local_skill_with_explicit_manifest_path(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Scenario: Custom manifest path."""
    pool = tmp_path / "pool"
    (pool / "audit").mkdir(parents=True)
    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude]
            sources:
              - name: local
                type: local
                path: {pool}
            skills: [audit]
        """),
    )
    result = runner.invoke(
        app, ["install", "--manifest", str(proj / "skillfile.yml")]
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    install_root = proj / ".skillpod" / "skills" / "audit"
    assert install_root.is_dir()
    assert not install_root.is_symlink()
    assert (proj / ".claude" / "skills" / "audit").is_symlink()


def test_install_unknown_agent_returns_user_error_code_1(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Scenario: Manifest validation failure returns code 1."""
    proj = _project(
        tmp_path,
        "version: 1\nagents: [foobar]\nskills: []\n",
    )
    result = runner.invoke(
        app, ["install", "--manifest", str(proj / "skillfile.yml")]
    )
    assert result.exit_code == 1


@respx.mock
def test_install_registry_timeout_returns_system_error_code_2(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Scenario: Registry timeout returns code 2."""
    respx.get(f"{_REGISTRY_BASE}/api/skills/audit").mock(
        side_effect=httpx.ConnectTimeout("nope")
    )
    proj = _project(
        tmp_path,
        textwrap.dedent("""
            version: 1
            agents: [claude]
            skills: [audit]
        """),
    )
    result = runner.invoke(
        app, ["install", "--manifest", str(proj / "skillfile.yml")]
    )
    assert result.exit_code == 2


# ---- add / remove (atomic round-trip) --------------------------------------


def test_add_then_remove_round_trip(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Scenario: `add` updates manifest and lockfile atomically +
    Scenario: `remove` deletes materialised state."""
    pool = tmp_path / "pool"
    (pool / "audit").mkdir(parents=True)
    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude]
            sources:
              - name: local
                type: local
                path: {pool}
            skills: []
        """),
    )

    add_result = runner.invoke(
        app, ["add", "audit", "--manifest", str(proj / "skillfile.yml")]
    )
    assert add_result.exit_code == 0, add_result.stdout + add_result.stderr
    manifest_after_add = (proj / "skillfile.yml").read_text(encoding="utf-8")
    assert "audit" in manifest_after_add
    install_root = proj / ".skillpod" / "skills" / "audit"
    assert install_root.is_dir()
    assert not install_root.is_symlink()
    assert (proj / ".claude" / "skills" / "audit").is_symlink()

    remove_result = runner.invoke(
        app, ["remove", "audit", "--manifest", str(proj / "skillfile.yml")]
    )
    assert remove_result.exit_code == 0, remove_result.stdout + remove_result.stderr
    assert not (proj / ".skillpod" / "skills" / "audit").exists()
    assert not (proj / ".claude" / "skills" / "audit").exists()
    final_manifest = (proj / "skillfile.yml").read_text(encoding="utf-8")
    assert "- audit" not in final_manifest


def test_add_failure_does_not_mutate_manifest(
    runner: CliRunner, tmp_path: Path
) -> None:
    """`add` must restore the manifest if install fails."""
    proj = _project(
        tmp_path,
        textwrap.dedent("""
            version: 1
            agents: [claude]
            skills: []
        """),
    )
    snapshot = (proj / "skillfile.yml").read_text(encoding="utf-8")

    # No sources, no registry mocked → `add` should fail at the install step.
    result = runner.invoke(
        app, ["add", "ghost", "--manifest", str(proj / "skillfile.yml")]
    )
    assert result.exit_code != 0
    assert (proj / "skillfile.yml").read_text(encoding="utf-8") == snapshot


def test_add_rejects_duplicate_skill(
    runner: CliRunner, tmp_path: Path
) -> None:
    pool = tmp_path / "pool"
    (pool / "audit").mkdir(parents=True)
    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude]
            sources:
              - name: local
                type: local
                path: {pool}
            skills: [audit]
        """),
    )
    result = runner.invoke(
        app, ["add", "audit", "--manifest", str(proj / "skillfile.yml")]
    )
    assert result.exit_code == 1
    assert "already" in (result.stdout + result.stderr).lower()


def test_remove_unknown_skill_errors(
    runner: CliRunner, tmp_path: Path
) -> None:
    proj = _project(tmp_path, "version: 1\nagents: [claude]\nskills: []\n")
    result = runner.invoke(
        app, ["remove", "ghost", "--manifest", str(proj / "skillfile.yml")]
    )
    assert result.exit_code == 1


# ---- list ------------------------------------------------------------------


def test_list_json_output_is_valid_json(runner: CliRunner, tmp_path: Path) -> None:
    """Scenario: JSON output for `list`."""
    pool = tmp_path / "pool"
    (pool / "audit").mkdir(parents=True)
    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude]
            sources:
              - name: local
                type: local
                path: {pool}
            skills: [audit]
        """),
    )
    runner.invoke(app, ["install", "--manifest", str(proj / "skillfile.yml")])

    result = runner.invoke(
        app, ["list", "--json", "--manifest", str(proj / "skillfile.yml")]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["agents"] == ["claude"]
    assert {s["name"] for s in payload["skills"]} == {"audit"}


# ---- sync ------------------------------------------------------------------


def test_sync_recreates_from_lockfile_idempotently(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Scenario: `sync` is idempotent against the lockfile."""
    repo_path, _sha = make_skill_repo(tmp_path / "git-side")
    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude, codex]
            sources:
              - name: anthropic
                type: git
                url: {repo_path}
                ref: main
            skills:
              - name: audit
                source: anthropic
        """),
    )
    # First install populates the lockfile.
    install_result = runner.invoke(
        app, ["install", "--manifest", str(proj / "skillfile.yml")]
    )
    assert install_result.exit_code == 0, install_result.stdout + install_result.stderr

    # Wipe the materialised tree but keep the lockfile.
    for path in [".skillpod", ".claude", ".codex"]:
        full = proj / path
        if full.exists():
            import shutil
            shutil.rmtree(full)

    sync_result = runner.invoke(
        app, ["sync", "--manifest", str(proj / "skillfile.yml")]
    )
    assert sync_result.exit_code == 0, sync_result.stdout + sync_result.stderr
    install_root = proj / ".skillpod" / "skills" / "audit"
    assert install_root.is_dir()
    assert not install_root.is_symlink()
    assert (proj / ".claude" / "skills" / "audit").is_symlink()
    assert (proj / ".codex" / "skills" / "audit").is_symlink()

    # Running sync again should be a no-op (no errors, same shape).
    sync_again = runner.invoke(
        app, ["sync", "--manifest", str(proj / "skillfile.yml")]
    )
    assert sync_again.exit_code == 0


@respx.mock
def test_sync_does_not_call_registry(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Sync must not consult the registry — pin a route that would 500
    if hit, and assert it is never called."""
    repo_path, _sha = make_skill_repo(tmp_path / "git-side")
    route = respx.get(f"{_REGISTRY_BASE}/api/skills/audit").mock(
        return_value=httpx.Response(500, text="must not be called")
    )
    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude]
            sources:
              - name: anthropic
                type: git
                url: {repo_path}
                ref: main
            skills:
              - name: audit
                source: anthropic
        """),
    )
    runner.invoke(app, ["install", "--manifest", str(proj / "skillfile.yml")])
    sync_result = runner.invoke(
        app, ["sync", "--manifest", str(proj / "skillfile.yml")]
    )
    assert sync_result.exit_code == 0
    assert not route.called


# ---- search -----------------------------------------------------------------


def _search_payload(*hits: dict[str, Any]) -> dict[str, Any]:
    return {
        "query": hits[0]["name"] if hits else "",
        "searchType": "fuzzy",
        "skills": list(hits),
        "count": len(hits),
        "duration_ms": 0,
    }


@respx.mock
def test_search_returns_one_row_for_matching_skill(
    runner: CliRunner, tmp_path: Path
) -> None:
    """search: /api/search hit → one row rendered with installs."""
    respx.get(f"{_REGISTRY_BASE}/api/search").mock(
        return_value=httpx.Response(
            200,
            json=_search_payload(
                {
                    "id": "vercel-labs/agent-skills/audit",
                    "skillId": "audit",
                    "name": "audit",
                    "installs": 5000,
                    "source": "vercel-labs/agent-skills",
                }
            ),
        )
    )
    proj = tmp_path / "project"
    proj.mkdir()
    result = runner.invoke(app, ["search", "audit", "--manifest", str(proj / "skillfile.yml")])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "audit" in result.stdout
    assert "vercel-labs/agent-skills" in result.stdout


@respx.mock
def test_search_json_shape_stable(
    runner: CliRunner, tmp_path: Path
) -> None:
    """search --json: output exposes name/repo/installs and trust columns."""
    respx.get(f"{_REGISTRY_BASE}/api/search").mock(
        return_value=httpx.Response(
            200,
            json=_search_payload(
                {
                    "id": "vercel-labs/agent-skills/audit",
                    "skillId": "audit",
                    "name": "audit",
                    "installs": 5000,
                    "source": "vercel-labs/agent-skills",
                }
            ),
        )
    )
    proj = tmp_path / "project"
    proj.mkdir()
    result = runner.invoke(
        app, ["search", "audit", "--json", "--manifest", str(proj / "skillfile.yml")]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["query"] == "audit"
    assert len(payload["results"]) == 1
    row = payload["results"][0]
    assert row["name"] == "audit"
    assert row["repo"] == "https://github.com/vercel-labs/agent-skills"
    assert row["source"] == "vercel-labs/agent-skills"
    assert row["installs"] == 5000
    # Search API does not expose verified/stars — they surface as null.
    assert row["stars"] is None
    assert row["verified"] is None
    assert "passes_policy" in row


@respx.mock
def test_search_not_found_returns_zero_rows(
    runner: CliRunner, tmp_path: Path
) -> None:
    """search: empty `skills` list → 0 rows, exit 0."""
    respx.get(f"{_REGISTRY_BASE}/api/search").mock(
        return_value=httpx.Response(
            200,
            json={"query": "ghost", "skills": [], "count": 0},
        )
    )
    proj = tmp_path / "project"
    proj.mkdir()
    result = runner.invoke(app, ["search", "ghost", "--manifest", str(proj / "skillfile.yml")])
    assert result.exit_code == 0


@respx.mock
def test_search_marks_policy_failing_row(
    runner: CliRunner, tmp_path: Path
) -> None:
    """search: default strict policy → passes_policy=false (verified unknown), still shown."""
    respx.get(f"{_REGISTRY_BASE}/api/search").mock(
        return_value=httpx.Response(
            200,
            json=_search_payload(
                {
                    "id": "vercel-labs/agent-skills/audit",
                    "skillId": "audit",
                    "name": "audit",
                    "installs": 0,
                    "source": "vercel-labs/agent-skills",
                }
            ),
        )
    )
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "skillfile.yml").write_text(
        "version: 1\nagents: []\nskills: []\n", encoding="utf-8"
    )
    result = runner.invoke(
        app, ["search", "audit", "--json", "--manifest", str(proj / "skillfile.yml")]
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["results"][0]["passes_policy"] is False


# ---- outdated ---------------------------------------------------------------


def test_outdated_no_drift(runner: CliRunner, tmp_path: Path) -> None:
    """outdated: same commit in lock and HEAD → drift=no."""
    repo_path, sha = make_skill_repo(tmp_path / "git-side")
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "skillfile.yml").write_text(
        "version: 1\nagents: [claude]\nskills: []\n", encoding="utf-8"
    )
    # Write a lockfile with the exact current HEAD SHA.
    fake_sha256 = "a" * 64
    (proj / "skillfile.lock").write_text(
        textwrap.dedent(f"""
            version: 1
            resolved:
              audit:
                source: git
                url: {repo_path}
                commit: {sha}
                sha256: {fake_sha256}
        """).lstrip(),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["outdated", "--manifest", str(proj / "skillfile.yml")])
    assert result.exit_code == 0
    assert "no" in result.stdout  # drift=no


def test_outdated_with_drift(runner: CliRunner, tmp_path: Path) -> None:
    """outdated: lockfile commit != HEAD → drift=yes."""
    repo_path, _sha = make_skill_repo(tmp_path / "git-side")
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "skillfile.yml").write_text(
        "version: 1\nagents: [claude]\nskills: []\n", encoding="utf-8"
    )
    # Use a different (but valid-format) commit in the lockfile.
    locked_sha = "deadbeef" * 5  # 40 hex chars
    fake_sha256 = "a" * 64
    (proj / "skillfile.lock").write_text(
        textwrap.dedent(f"""
            version: 1
            resolved:
              audit:
                source: git
                url: {repo_path}
                commit: {locked_sha}
                sha256: {fake_sha256}
        """).lstrip(),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["outdated", "--manifest", str(proj / "skillfile.yml")])
    assert result.exit_code == 0
    assert "yes" in result.stdout  # drift=yes


def test_outdated_network_failure_exits_2(runner: CliRunner, tmp_path: Path) -> None:
    """outdated: ls-remote fails on bogus URL → exit 2."""
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "skillfile.yml").write_text(
        "version: 1\nagents: []\nskills: []\n", encoding="utf-8"
    )
    fake_sha256 = "b" * 64
    fake_sha = "cafebabe" * 5
    # Use a URL that git ls-remote will definitely fail on.
    (proj / "skillfile.lock").write_text(
        textwrap.dedent(f"""
            version: 1
            resolved:
              audit:
                source: git
                url: https://this-host-does-not-exist.invalid/repo.git
                commit: {fake_sha}
                sha256: {fake_sha256}
        """).lstrip(),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["outdated", "--manifest", str(proj / "skillfile.yml")])
    assert result.exit_code == 2


# ---- update -----------------------------------------------------------------


@respx.mock
def test_update_single_skill(runner: CliRunner, tmp_path: Path) -> None:
    """update audit: lockfile entry for audit is refreshed to the latest commit."""
    repo_path, sha = make_skill_repo(tmp_path / "git-side")
    respx.get(f"{_REGISTRY_BASE}/api/skills/audit").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "audit",
                "repo": {
                    "host": "github.com",
                    "org": "vercel-labs",
                    "name": "agent-skills",
                    "url": str(repo_path),
                },
                "ref": "main",
                "commit": sha,
                "meta": {"verified": True, "installs": 100, "stars": 10},
            },
        )
    )
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "skillfile.yml").write_text(
        "version: 1\nagents: []\nskills: [audit]\n", encoding="utf-8"
    )
    result = runner.invoke(
        app, ["update", "audit", "--manifest", str(proj / "skillfile.yml")]
    )
    assert result.exit_code == 0, result.stdout + result.stderr

    from skillpod.lockfile import io as lock_io
    lock = lock_io.read(proj / "skillfile.lock")
    # audit should now have the fresh SHA from the registry.
    assert lock.resolved["audit"].commit == sha


@respx.mock
def test_update_aborts_on_trust_failure(runner: CliRunner, tmp_path: Path) -> None:
    """update: TrustError → exit 1, lockfile unchanged."""
    from tests._git_fixtures import make_skill_repo as _make
    repo_path, sha = _make(tmp_path / "git-side")
    respx.get(f"{_REGISTRY_BASE}/api/skills/audit").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "audit",
                "repo": {
                    "host": "github.com",
                    "org": "vercel-labs",
                    "name": "agent-skills",
                    "url": str(repo_path),
                },
                "ref": "main",
                "commit": sha,
                "meta": {"verified": False, "installs": 0, "stars": 0},
            },
        )
    )
    proj = tmp_path / "project"
    proj.mkdir()
    # Default policy blocks unverified skills.
    (proj / "skillfile.yml").write_text(
        "version: 1\nagents: []\nskills: [audit]\n", encoding="utf-8"
    )
    old_sha = "a" * 40
    fake_sha256 = "e" * 64
    lock_text = textwrap.dedent(f"""
        version: 1
        resolved:
          audit:
            source: git
            url: {repo_path}
            commit: {old_sha}
            sha256: {fake_sha256}
    """).lstrip()
    (proj / "skillfile.lock").write_text(lock_text, encoding="utf-8")

    result = runner.invoke(
        app, ["update", "audit", "--manifest", str(proj / "skillfile.yml")]
    )
    assert result.exit_code == 1

    # Lockfile restored to original.
    from skillpod.lockfile import io as lock_io
    lock = lock_io.read(proj / "skillfile.lock")
    assert lock.resolved["audit"].commit == old_sha


# ---- doctor -----------------------------------------------------------------


def test_doctor_clean_project(runner: CliRunner, tmp_path: Path) -> None:
    """doctor: freshly installed project → no findings, exit 0."""
    pool = tmp_path / "pool"
    (pool / "audit").mkdir(parents=True)
    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude]
            sources:
              - name: local
                type: local
                path: {pool}
            skills: [audit]
        """),
    )
    runner.invoke(app, ["install", "--manifest", str(proj / "skillfile.yml")])
    result = runner.invoke(app, ["doctor", "--manifest", str(proj / "skillfile.yml")])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "healthy" in result.stdout.lower() or "no findings" in result.stdout.lower()


def test_doctor_missing_symlink(runner: CliRunner, tmp_path: Path) -> None:
    """doctor: missing fanout symlink → error finding, exit 1."""
    pool = tmp_path / "pool"
    (pool / "audit").mkdir(parents=True)
    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude]
            sources:
              - name: local
                type: local
                path: {pool}
            skills: [audit]
        """),
    )
    runner.invoke(app, ["install", "--manifest", str(proj / "skillfile.yml")])
    # Delete the fanout symlink to simulate breakage.
    (proj / ".claude" / "skills" / "audit").unlink()
    result = runner.invoke(app, ["doctor", "--manifest", str(proj / "skillfile.yml")])
    assert result.exit_code == 1
    assert "error" in result.stdout.lower() or "missing" in result.stdout.lower()


def test_doctor_orphan_dir(runner: CliRunner, tmp_path: Path) -> None:
    """doctor: orphan under .skillpod/skills/ → warning, exit 0."""
    pool = tmp_path / "pool"
    (pool / "audit").mkdir(parents=True)
    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude]
            sources:
              - name: local
                type: local
                path: {pool}
            skills: [audit]
        """),
    )
    runner.invoke(app, ["install", "--manifest", str(proj / "skillfile.yml")])
    # Create an orphan.
    (proj / ".skillpod" / "skills" / "legacy").mkdir(parents=True, exist_ok=True)
    result = runner.invoke(app, ["doctor", "--manifest", str(proj / "skillfile.yml")])
    assert result.exit_code == 0  # warning only, no error
    assert "orphan" in result.stdout.lower() or "legacy" in result.stdout.lower()


def test_doctor_lockfile_drift(runner: CliRunner, tmp_path: Path) -> None:
    """doctor: manifest skill not in lockfile → error finding, exit 1."""
    pool = tmp_path / "pool"
    (pool / "audit").mkdir(parents=True)
    _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: []
            sources:
              - name: local
                type: local
                path: {pool}
            skills: [audit]
        """),
    )
    # Do NOT install; lockfile will be missing the entry.
    # (local-sourced skills don't get lock entries, so we need a non-local manifest.)
    # For this test use a git URL that happens to be the pool - doesn't matter because
    # we just want to check that a skill without source=local AND without a lock entry
    # triggers an error.  Use a manifest with no sources (registry fallback).
    proj2 = tmp_path / "project2"
    proj2.mkdir()
    (proj2 / "skillfile.yml").write_text(
        "version: 1\nagents: []\nskills: [audit]\n", encoding="utf-8"
    )
    # Empty lockfile (no resolved entries).
    (proj2 / "skillfile.lock").write_text("version: 1\nresolved: {}\n", encoding="utf-8")
    result = runner.invoke(app, ["doctor", "--manifest", str(proj2 / "skillfile.yml")])
    assert result.exit_code == 1
    assert "error" in result.stdout.lower() or "lockfile" in result.stdout.lower()


def test_doctor_schema_hints_flag_human_mode(
    runner: CliRunner, tmp_path: Path
) -> None:
    proj = _project(tmp_path, "version: 1\nskills: []\n")
    (proj / "skillfile.lock").write_text("version: 1\nresolved: {}\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["doctor", "--schema-hints", "--manifest", str(proj / "skillfile.yml")],
    )

    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Schema hints:" in result.stdout
    assert any(
        "default" in line and "agents" in line
        for line in result.stdout.splitlines()
    )


def test_doctor_schema_hints_flag_json_mode(
    runner: CliRunner, tmp_path: Path
) -> None:
    proj = _project(tmp_path, "version: 1\nskills: []\n")
    (proj / "skillfile.lock").write_text("version: 1\nresolved: {}\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "doctor",
            "--schema-hints",
            "--json",
            "--manifest",
            str(proj / "skillfile.yml"),
        ],
    )

    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert isinstance(payload["schema_hints"], list)
    assert payload["schema_hints"]
    for item in payload["schema_hints"]:
        assert set(item) == {"field", "explicit", "value_summary"}
    version = next(item for item in payload["schema_hints"] if item["field"] == "version")
    assert version["explicit"] is True


# ---- global advisory --------------------------------------------------------


def test_global_list_against_fake_home(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".claude" / "skills" / "audit").mkdir(parents=True)
    (tmp_path / ".codex" / "skills" / "polish").mkdir(parents=True)

    result = runner.invoke(app, ["global", "list", "--json"])

    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert {(row["agent"], row["name"]) for row in payload} == {
        ("claude", "audit"),
        ("codex", "polish"),
    }
    assert all({"agent", "name", "path", "size_bytes", "mtime"} <= set(row) for row in payload)


def _archive_project(tmp_path: Path) -> Path:
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "skillfile.yml").write_text("version: 1\nskills: []\n", encoding="utf-8")
    return proj


def test_global_archive_moves_to_skillpod_home(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    skill_dir = tmp_path / ".claude" / "skills" / "audit"
    skill_dir.mkdir(parents=True)
    (skill_dir / "manifest.md").write_text("# audit", encoding="utf-8")
    monkeypatch.chdir(_archive_project(tmp_path))

    result = runner.invoke(app, ["global", "archive", "audit", "--json"])

    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    dest = tmp_path / ".skillpod" / "skills" / "audit"
    assert payload["ok"] is True
    assert payload["dest"] == str(dest)
    assert payload["moved_from"] == [str(skill_dir)]
    assert payload["skipped_existing"] is False
    assert not skill_dir.exists()
    assert (dest / "manifest.md").read_text(encoding="utf-8") == "# audit"
    # No leftover archived-* renames in agent dir.
    assert not list((tmp_path / ".claude" / "skills").glob("audit.archived-*"))


def test_global_archive_idempotent_when_dest_matches(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    dest = tmp_path / ".skillpod" / "skills" / "audit"
    dest.mkdir(parents=True)
    (dest / "manifest.md").write_text("# audit", encoding="utf-8")
    agent_copy = tmp_path / ".claude" / "skills" / "audit"
    agent_copy.mkdir(parents=True)
    (agent_copy / "manifest.md").write_text("# audit", encoding="utf-8")
    monkeypatch.chdir(_archive_project(tmp_path))

    result = runner.invoke(app, ["global", "archive", "audit", "--json"])

    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["skipped_existing"] is True
    assert payload["moved_from"] == []
    assert payload["removed"] == [str(agent_copy)]
    assert (dest / "manifest.md").read_text(encoding="utf-8") == "# audit"
    assert not agent_copy.exists()


def test_global_archive_conflict_without_force(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    dest = tmp_path / ".skillpod" / "skills" / "audit"
    dest.mkdir(parents=True)
    (dest / "manifest.md").write_text("# old", encoding="utf-8")
    agent_copy = tmp_path / ".claude" / "skills" / "audit"
    agent_copy.mkdir(parents=True)
    (agent_copy / "manifest.md").write_text("# new", encoding="utf-8")
    monkeypatch.chdir(_archive_project(tmp_path))

    result = runner.invoke(app, ["global", "archive", "audit"])

    assert result.exit_code != 0
    assert "different content" in (result.stdout + result.stderr)
    assert (dest / "manifest.md").read_text(encoding="utf-8") == "# old"
    assert (agent_copy / "manifest.md").read_text(encoding="utf-8") == "# new"


def test_global_archive_force_overwrites(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    dest = tmp_path / ".skillpod" / "skills" / "audit"
    dest.mkdir(parents=True)
    (dest / "manifest.md").write_text("# old", encoding="utf-8")
    agent_copy = tmp_path / ".claude" / "skills" / "audit"
    agent_copy.mkdir(parents=True)
    (agent_copy / "manifest.md").write_text("# new", encoding="utf-8")
    monkeypatch.chdir(_archive_project(tmp_path))

    result = runner.invoke(app, ["global", "archive", "audit", "--force", "--json"])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert (dest / "manifest.md").read_text(encoding="utf-8") == "# new"
    assert not agent_copy.exists()


def test_global_archive_unlinks_managed_symlink(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    dest = tmp_path / ".skillpod" / "skills" / "audit"
    dest.mkdir(parents=True)
    (dest / "manifest.md").write_text("# audit", encoding="utf-8")
    claude_dir = tmp_path / ".claude" / "skills"
    claude_dir.mkdir(parents=True)
    link = claude_dir / "audit"
    link.symlink_to(dest)
    monkeypatch.chdir(_archive_project(tmp_path))

    result = runner.invoke(app, ["global", "archive", "audit", "--json"])

    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["unlinked"] == [str(link)]
    assert payload["moved_from"] == []
    assert payload["skipped_existing"] is True
    assert (dest / "manifest.md").read_text(encoding="utf-8") == "# audit"
    assert not link.exists() and not link.is_symlink()


def test_global_archive_multi_agent_same_content(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    claude_copy = tmp_path / ".claude" / "skills" / "audit"
    claude_copy.mkdir(parents=True)
    (claude_copy / "manifest.md").write_text("# audit", encoding="utf-8")
    codex_copy = tmp_path / ".codex" / "skills" / "audit"
    codex_copy.mkdir(parents=True)
    (codex_copy / "manifest.md").write_text("# audit", encoding="utf-8")
    monkeypatch.chdir(_archive_project(tmp_path))

    result = runner.invoke(app, ["global", "archive", "audit", "--json"])

    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    dest = tmp_path / ".skillpod" / "skills" / "audit"
    assert payload["moved_from"] == [str(claude_copy)]
    assert payload["removed"] == [str(codex_copy)]
    assert (dest / "manifest.md").read_text(encoding="utf-8") == "# audit"
    assert not claude_copy.exists()
    assert not codex_copy.exists()


def test_global_doctor_flags_duplicate(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".claude" / "skills" / "audit").mkdir(parents=True)
    (tmp_path / ".codex" / "skills" / "audit").mkdir(parents=True)
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "skillfile.yml").write_text("version: 1\nskills: []\n", encoding="utf-8")

    result = runner.invoke(
        app, ["global", "doctor", "--json", "--manifest", str(proj / "skillfile.yml")]
    )

    assert result.exit_code == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert any(f["code"] == "duplicate-global-skill" for f in payload["findings"])


def test_global_doctor_flags_global_local_conflict(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".claude" / "skills" / "audit").mkdir(parents=True)
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "skillfile.yml").write_text("version: 1\nskills: []\n", encoding="utf-8")
    (proj / "skillfile.lock").write_text(
        textwrap.dedent("""
            version: 1
            resolved:
              audit:
                source: git
                url: https://example.invalid/audit.git
                commit: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
                sha256: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
        """).lstrip(),
        encoding="utf-8",
    )

    result = runner.invoke(
        app, ["global", "doctor", "--json", "--manifest", str(proj / "skillfile.yml")]
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert any(f["code"] == "global-local-conflict" for f in payload["findings"])


def test_global_doctor_flags_broken_symlink(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    skill_link = tmp_path / ".claude" / "skills" / "ghost"
    skill_link.parent.mkdir(parents=True)
    skill_link.symlink_to(tmp_path / "missing-target")
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / "skillfile.yml").write_text("version: 1\nskills: []\n", encoding="utf-8")

    result = runner.invoke(
        app, ["global", "doctor", "--json", "--manifest", str(proj / "skillfile.yml")]
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert any(f["code"] == "broken-global-symlink" for f in payload["findings"])


# ---- adapter list -----------------------------------------------------------


def test_adapter_list_json_shape_default_identity(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Scenario: Default registry shown — every agent shows IdentityAdapter."""
    proj = _project(
        tmp_path,
        "version: 1\nagents: [claude, codex, gemini]\nskills: []\n",
    )
    result = runner.invoke(
        app, ["adapter", "list", "--json", "--manifest", str(proj / "skillfile.yml")]
    )
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    adapters = payload["adapters"]
    assert len(adapters) == 3
    agent_names = [r["agent"] for r in adapters]
    assert agent_names == ["claude", "codex", "gemini"]
    for row in adapters:
        assert "IdentityAdapter" in row["adapter"]
        assert row["mode-supported"] == "symlink, copy, hardlink"


def test_adapter_list_exit_1_on_bad_adapter_path(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Scenario: Custom adapter dotted path fails to import — exit 1."""
    proj = _project(
        tmp_path,
        "version: 1\nagents:\n  - name: claude\n    adapter: nonexistent.module.Adapter\nskills: []\n",
    )
    result = runner.invoke(
        app, ["adapter", "list", "--json", "--manifest", str(proj / "skillfile.yml")]
    )
    assert result.exit_code == 1


def test_adapter_list_human_output_has_header(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Human-readable adapter list includes AGENT/ADAPTER/MODE-SUPPORTED header."""
    proj = _project(
        tmp_path,
        "version: 1\nagents: [claude]\nskills: []\n",
    )
    result = runner.invoke(
        app, ["adapter", "list", "--manifest", str(proj / "skillfile.yml")]
    )
    assert result.exit_code == 0, result.stdout
    assert "AGENT" in result.stdout
    assert "ADAPTER" in result.stdout
    assert "MODE-SUPPORTED" in result.stdout


# ---- sync --agent -----------------------------------------------------------


def test_sync_agent_flag_only_renders_target_agent(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Scenario: Single-agent re-render — only .claude/skills/ is touched."""
    skills_root = tmp_path / "pool"
    (skills_root / "audit").mkdir(parents=True)
    (skills_root / "audit" / "manifest.md").write_text("# audit", encoding="utf-8")

    proj = _project(
        tmp_path,
        textwrap.dedent(f"""
            version: 1
            agents: [claude, codex]
            sources:
              - name: local
                type: local
                path: {skills_root}
            skills: [audit]
        """),
    )

    # Full install first so both agents have fan-out.
    result = runner.invoke(
        app, ["install", "--manifest", str(proj / "skillfile.yml")]
    )
    assert result.exit_code == 0, result.stdout

    assert (proj / ".claude" / "skills" / "audit").exists()
    assert (proj / ".codex" / "skills" / "audit").exists()

    # Remove claude's fan-out manually; sync --agent claude should re-create it.
    (proj / ".claude" / "skills" / "audit").unlink()

    result = runner.invoke(
        app,
        ["sync", "--agent", "claude", "--manifest", str(proj / "skillfile.yml")],
    )
    assert result.exit_code == 0, result.stdout

    # claude's fan-out is restored.
    assert (proj / ".claude" / "skills" / "audit").exists()
    # codex is untouched (still present from install).
    assert (proj / ".codex" / "skills" / "audit").exists()


def test_sync_unknown_agent_exits_1(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Scenario: Unknown agent rejected — exit 1, no fan-out touched."""
    proj = _project(
        tmp_path,
        "version: 1\nagents: [claude]\nskills: []\n",
    )
    result = runner.invoke(
        app,
        ["sync", "--agent", "foobar", "--manifest", str(proj / "skillfile.yml")],
    )
    assert result.exit_code == 1


def test_schema_command_writes_valid_json(runner: CliRunner, tmp_path: Path) -> None:
    output = tmp_path / "out.json"

    result = runner.invoke(app, ["schema", "--output", str(output)])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert output.exists()
    with output.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    assert "$schema" in schema
    assert "properties" in schema
    assert "version" in schema["properties"]
    assert "agents" in schema["properties"]
    assert "skills" in schema["properties"]
