"""Tests for composing global profiles into one source-bearing body and
applying the union via `switch <a>+<b> --scope global`."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from skillpod.cli.commands import switch
from skillpod.installer.paths import (
    global_agent_skill_dir,
    global_skill_dir,
    is_managed_global_fanout,
)
from skillpod.profile.compose import compose_global_bodies
from skillpod.profile.errors import ProfileError
from tests._git_fixtures import make_root_skill_repo


def _write_global_profile(home: Path, name: str, body: dict) -> None:
    root = home / ".skillpod" / "profiles"
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{name}.yml").write_text(
        yaml.safe_dump({"version": 1, "profile": body}, sort_keys=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# compose_global_bodies — union semantics (unit)
# ---------------------------------------------------------------------------


def test_compose_unions_source_bearing_skills(tmp_path: Path) -> None:
    _write_global_profile(
        tmp_path, "dev", {"skills": [{"name": "audit", "source": "o/audit"}]}
    )
    _write_global_profile(
        tmp_path,
        "reviewer",
        {"skills": [{"name": "polish", "source": "o/polish", "ref": "main",
                     "subpath": "skills/polish"}]},
    )

    expr, body = compose_global_bodies("dev+reviewer", home=tmp_path)

    assert expr == "dev+reviewer"
    assert [s.name for s in body.skills] == ["audit", "polish"]
    polish = body.skills[1]
    assert (polish.source, polish.ref, polish.subpath) == (
        "o/polish", "main", "skills/polish"
    )


def test_compose_left_wins_on_conflicting_source_with_warning(tmp_path: Path) -> None:
    _write_global_profile(tmp_path, "dev", {"skills": [{"name": "polish", "source": "o/a"}]})
    _write_global_profile(tmp_path, "reviewer", {"skills": [{"name": "polish", "source": "o/b"}]})

    with pytest.warns(UserWarning, match="conflicting sources"):
        _expr, body = compose_global_bodies("dev+reviewer", home=tmp_path)

    assert [s.name for s in body.skills] == ["polish"]
    assert body.skills[0].source == "o/a"  # leftmost operand wins


def test_compose_same_source_dedup_no_warning(
    tmp_path: Path, recwarn: pytest.WarningsRecorder
) -> None:
    _write_global_profile(tmp_path, "dev", {"skills": [{"name": "polish", "source": "o/a"}]})
    _write_global_profile(tmp_path, "reviewer", {"skills": [{"name": "polish", "source": "o/a"}]})

    _expr, body = compose_global_bodies("dev+reviewer", home=tmp_path)

    assert [s.name for s in body.skills] == ["polish"]
    assert len(recwarn.list) == 0


def test_compose_unions_agents_preserving_first_order(tmp_path: Path) -> None:
    _write_global_profile(tmp_path, "dev", {"agents": ["claude"], "skills": []})
    _write_global_profile(tmp_path, "reviewer", {"agents": ["codex", "claude"], "skills": []})

    _expr, body = compose_global_bodies("dev+reviewer", home=tmp_path)

    assert body.agents == ["claude", "codex"]


def test_compose_rejects_remote_operand(tmp_path: Path) -> None:
    _write_global_profile(tmp_path, "dev", {"skills": []})

    with pytest.raises(ProfileError, match="local profile name"):
        compose_global_bodies("dev+https://example.com/x.yml", home=tmp_path)


def test_compose_missing_operand_raises(tmp_path: Path) -> None:
    _write_global_profile(tmp_path, "dev", {"skills": []})

    with pytest.raises(ProfileError):
        compose_global_bodies("dev+ghost", home=tmp_path)


# ---------------------------------------------------------------------------
# switch <a>+<b> --scope global — end-to-end with real git sources
# ---------------------------------------------------------------------------


def _switch(name: str, tmp_path: Path, home: Path, **kw: object) -> None:
    switch.run(
        name,
        "global",
        project_root=tmp_path,
        manifest_path=tmp_path / "skillfile.yml",  # absent → no project guard
        json_output=False,
        home=home,
        **kw,
    )


def test_switch_composite_global_downloads_both_and_records_expr(tmp_path: Path) -> None:
    audit_repo, _ = make_root_skill_repo(tmp_path / "src", repo_name="audit")
    polish_repo, _ = make_root_skill_repo(tmp_path / "src", repo_name="polish")
    home = tmp_path / "home"
    _write_global_profile(home, "dev", {"skills": [{"name": "audit", "source": str(audit_repo)}]})
    _write_global_profile(
        home, "reviewer", {"skills": [{"name": "polish", "source": str(polish_repo)}]}
    )

    _switch("dev+reviewer", tmp_path, home, agents=["claude"])

    for skill in ("audit", "polish"):
        assert global_skill_dir(skill, home).is_dir()
        assert is_managed_global_fanout(
            global_agent_skill_dir("claude", skill, home), skill, home
        )
    active = (home / ".skillpod" / "active-profile").read_text(encoding="utf-8").strip()
    assert active == "dev+reviewer"


def test_switch_back_after_composite_restores_previous(tmp_path: Path) -> None:
    audit_repo, _ = make_root_skill_repo(tmp_path / "src", repo_name="audit")
    polish_repo, _ = make_root_skill_repo(tmp_path / "src", repo_name="polish")
    home = tmp_path / "home"
    _write_global_profile(home, "dev", {"skills": [{"name": "audit", "source": str(audit_repo)}]})
    _write_global_profile(
        home, "reviewer", {"skills": [{"name": "polish", "source": str(polish_repo)}]}
    )

    # Start from a single profile, then switch to the composite (which snapshots it).
    _switch("dev", tmp_path, home, agents=["claude"])
    _switch("dev+reviewer", tmp_path, home, agents=["claude"])
    assert is_managed_global_fanout(
        global_agent_skill_dir("claude", "polish", home), "polish", home
    )

    # --back restores 'dev': audit stays, polish is unlinked, active reverts.
    _switch("dev", tmp_path, home, back=True)
    assert is_managed_global_fanout(
        global_agent_skill_dir("claude", "audit", home), "audit", home
    )
    assert not global_agent_skill_dir("claude", "polish", home).exists()
    active = (home / ".skillpod" / "active-profile").read_text(encoding="utf-8").strip()
    assert active == "dev"


def test_switch_composite_rejected_for_project_scope(tmp_path: Path) -> None:
    import typer

    _write_global_profile(tmp_path / "home", "dev", {"skills": []})
    with pytest.raises(typer.Exit) as exc_info:
        switch.run(
            "dev+reviewer",
            "project",
            project_root=tmp_path,
            manifest_path=tmp_path / "skillfile.yml",
            json_output=False,
            home=tmp_path / "home",
        )
    assert exc_info.value.exit_code == 1
