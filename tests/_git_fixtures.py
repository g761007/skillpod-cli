"""Helpers for building real git repositories inside `tmp_path`.

We deliberately use the real `git` binary rather than mocking it: the
source-resolver scenarios in `source-resolver/spec.md` make claims about
on-disk artefacts (cache layout, immutability), which a mock would fake.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _git(repo: Path, *args: str) -> str:
    env = {
        "GIT_AUTHOR_NAME": "skillpod-tests",
        "GIT_AUTHOR_EMAIL": "tests@skillpod.invalid",
        "GIT_COMMITTER_NAME": "skillpod-tests",
        "GIT_COMMITTER_EMAIL": "tests@skillpod.invalid",
        "PATH": __import__("os").environ.get("PATH", ""),
        "HOME": str(repo),  # avoid the user's global git config bleeding in
    }
    out = subprocess.run(
        ("git", *args),
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return out.stdout


def make_skill_repo(
    parent: Path,
    *,
    repo_name: str = "skills",
    skill_name: str = "audit",
    skill_files: dict[str, str] | None = None,
    branch: str = "main",
) -> tuple[Path, str]:
    """Create a single-commit git repo containing one skill directory.

    Returns ``(repo_path, commit_sha)`` where ``repo_path`` is suitable
    for use as a ``file://`` git URL or a direct filesystem path.
    """
    repo = parent / repo_name
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", branch)

    skill = repo / skill_name
    skill.mkdir()
    files = skill_files or {"manifest.md": f"# {skill_name}\n"}
    for rel, content in files.items():
        target = skill / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", f"add {skill_name}")
    sha = _git(repo, "rev-parse", "HEAD").strip()
    return repo, sha


def make_root_skill_repo(
    parent: Path,
    *,
    repo_name: str = "single-skill",
    skill_files: dict[str, str] | None = None,
    branch: str = "main",
) -> tuple[Path, str]:
    """Create a single-commit git repo whose root *is* the skill.

    The repo's top-level contains ``SKILL.md`` directly (no subdir),
    matching the "owner/repo points at one skill" shape that
    `skillpod add owner/repo` should treat as a single skill.
    """
    repo = parent / repo_name
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", branch)

    files = skill_files or {"SKILL.md": f"---\ndescription: {repo_name}\n---\n# {repo_name}\n"}
    if "SKILL.md" not in files:
        files = {"SKILL.md": f"---\ndescription: {repo_name}\n---\n# {repo_name}\n", **files}
    for rel, content in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", f"add root skill {repo_name}")
    sha = _git(repo, "rev-parse", "HEAD").strip()
    return repo, sha


__all__ = ["make_root_skill_repo", "make_skill_repo"]
