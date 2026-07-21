"""Tests for install records (`installed.yml`).

Phase 1a of `plans/2026-07-21-recommendation-model.md`. Nothing consumes the
record yet — these tests pin the schema's *semantics* before the switchover,
in particular the two ways a record deliberately differs from the lockfile it
replaces: local sources are representable, and so is unknown provenance.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from skillpod import record
from skillpod.installer.paths import global_record_path, project_record_path
from skillpod.record import InstallRecord, RecordError, SkillRecord

_COMMIT = "a" * 40
_SHA = "b" * 64


def _git(**overrides: object) -> SkillRecord:
    payload: dict[str, object] = {
        "kind": "git",
        "source": "https://github.com/o/r",
        "ref": "main",
        "commit": _COMMIT,
        "sha256": _SHA,
    }
    payload.update(overrides)
    return SkillRecord.model_validate(payload)


# ---- what a record can express that a lockfile could not -------------------


def test_local_source_is_recordable() -> None:
    """The lockfile refused local sources because it could not pin them.

    A record has nothing to pin — it states what is on disk, and a
    local-sourced skill is just as installed as a git-sourced one.
    """
    entry = SkillRecord.model_validate(
        {"kind": "local", "source": "/srv/skills/audit", "sha256": _SHA}
    )
    assert entry.kind == "local"
    assert entry.commit is None


def test_unknown_provenance_is_recordable() -> None:
    """Skills moved in by `global archive` have no recoverable origin.

    Recording them as `unknown` is what lets `global update` report them
    instead of silently pretending they do not exist.
    """
    entry = SkillRecord.model_validate({"kind": "unknown"})
    assert entry.source is None


def test_unknown_must_not_carry_provenance() -> None:
    """`unknown` means 'we do not know', not 'we half know'."""
    with pytest.raises(ValueError, match="must not carry"):
        SkillRecord.model_validate({"kind": "unknown", "source": "o/r"})


# ---- field validation ------------------------------------------------------


def test_git_requires_source_and_commit() -> None:
    with pytest.raises(ValueError, match="requires `commit`"):
        SkillRecord.model_validate({"kind": "git", "source": "o/r"})
    with pytest.raises(ValueError, match="requires `source`"):
        SkillRecord.model_validate({"kind": "git", "commit": _COMMIT})


def test_local_must_not_carry_commit() -> None:
    with pytest.raises(ValueError, match="must not set `commit`"):
        SkillRecord.model_validate(
            {"kind": "local", "source": "/srv/x", "commit": _COMMIT}
        )


def test_short_commit_rejected() -> None:
    with pytest.raises(ValueError):
        _git(commit="abc123")


def test_non_hex_sha256_rejected() -> None:
    with pytest.raises(ValueError, match="sha256"):
        _git(sha256="z" * 64)


def test_unknown_key_rejected() -> None:
    """Typos must surface rather than being silently dropped."""
    with pytest.raises(ValueError):
        SkillRecord.model_validate({"kind": "git", "sourse": "o/r", "commit": _COMMIT})


# ---- serialisation ---------------------------------------------------------


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "installed.yml"
    model = InstallRecord(installed={"audit": _git(), "polish": SkillRecord(kind="unknown")})
    record.write(path, model)
    assert record.read(path) == model


def test_names_sorted_and_fields_canonically_ordered(tmp_path: Path) -> None:
    """A record is rewritten on every install; unstable ordering would make
    it churn for no reason."""
    path = tmp_path / "installed.yml"
    record.write(
        path,
        InstallRecord(installed={"zeta": _git(), "alpha": _git()}),
    )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert list(raw["installed"]) == ["alpha", "zeta"]
    assert list(raw["installed"]["alpha"]) == ["kind", "source", "ref", "commit", "sha256"]


def test_unset_fields_are_omitted(tmp_path: Path) -> None:
    """An `unknown` entry should read as one line, not five nulls."""
    path = tmp_path / "installed.yml"
    record.write(path, InstallRecord(installed={"mystery": SkillRecord(kind="unknown")}))
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["installed"]["mystery"] == {"kind": "unknown"}


def test_write_creates_parent_directory(tmp_path: Path) -> None:
    """Records are written into `.skillpod/`, which may not exist yet."""
    path = tmp_path / "fresh" / ".skillpod" / "installed.yml"
    record.write(path, InstallRecord())
    assert path.is_file()


# ---- reading edge cases ----------------------------------------------------


def test_missing_file_returns_empty_record(tmp_path: Path) -> None:
    """Absence means 'nothing installed yet', not an error."""
    assert record.read(tmp_path / "nope.yml") == InstallRecord()


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    path = tmp_path / "installed.yml"
    path.write_text("installed: [unclosed\n", encoding="utf-8")
    with pytest.raises(RecordError, match="invalid YAML"):
        record.read(path)


def test_non_mapping_top_level_raises(tmp_path: Path) -> None:
    path = tmp_path / "installed.yml"
    path.write_text("- not a mapping\n", encoding="utf-8")
    with pytest.raises(RecordError, match="mapping"):
        record.read(path)


def test_invalid_entry_raises(tmp_path: Path) -> None:
    path = tmp_path / "installed.yml"
    path.write_text(
        yaml.safe_dump({"version": 1, "installed": {"audit": {"kind": "git"}}}),
        encoding="utf-8",
    )
    with pytest.raises(RecordError):
        record.read(path)


# ---- paths -----------------------------------------------------------------


def test_record_paths_live_under_skillpod_dir(tmp_path: Path) -> None:
    """Both records sit inside `.skillpod/`, which init already gitignores —
    that is what keeps them off every developer's commit."""
    assert project_record_path(tmp_path) == tmp_path / ".skillpod" / "installed.yml"
    assert global_record_path(tmp_path) == tmp_path / ".skillpod" / "installed.yml"
