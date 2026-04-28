"""Unit tests for `skillpod.sources.spec.parse_source_spec`."""

from __future__ import annotations

import pytest

from skillpod.sources.spec import (
    SourceSpec,
    derive_unique_name,
    parse_source_spec,
)


@pytest.mark.parametrize(
    ("text", "expected_kind", "expected_url", "expected_name"),
    [
        # GitHub shorthand
        ("anthropics/skills", "git", "https://github.com/anthropics/skills", "skills"),
        ("vercel-labs/agent-skills", "git", "https://github.com/vercel-labs/agent-skills", "agent-skills"),
        # Full git URLs
        ("https://github.com/anthropics/skills", "git", "https://github.com/anthropics/skills", "skills"),
        ("https://github.com/anthropics/skills.git", "git", "https://github.com/anthropics/skills.git", "skills"),
        ("git+ssh://git@example.com/foo/bar.git", "git", "git+ssh://git@example.com/foo/bar.git", "bar"),
        # SCP-style git
        ("git@github.com:anthropics/skills.git", "git", "git@github.com:anthropics/skills.git", "skills"),
        ("git@github.com:anthropics/skills", "git", "git@github.com:anthropics/skills", "skills"),
        # .git suffix without scheme
        ("foo.git", "git", "foo.git", "foo"),
        # Local paths
        ("./my-skills", "local", "my-skills", "my-skills"),
        ("../shared/skills", "local", "../shared/skills", "skills"),
        ("/absolute/path/skills", "local", "/absolute/path/skills", "skills"),
    ],
)
def test_parse_recognises_source_forms(
    text: str, expected_kind: str, expected_url: str, expected_name: str
) -> None:
    spec = parse_source_spec(text)
    assert spec is not None, f"expected source for {text!r}"
    assert spec.kind == expected_kind
    if expected_kind == "local":
        # Local paths get expanduser-resolved; only assert the suffix matches.
        assert spec.url_or_path.endswith(expected_url) or spec.url_or_path == expected_url
    else:
        assert spec.url_or_path == expected_url
    assert spec.derived_name == expected_name


@pytest.mark.parametrize(
    "text",
    [
        "audit",
        "polish",
        "skill_creator",
        "frontend-design",
        "x",
    ],
)
def test_parse_returns_none_for_bare_skill_names(text: str) -> None:
    assert parse_source_spec(text) is None


def test_parse_strips_whitespace() -> None:
    spec = parse_source_spec("  anthropics/skills  ")
    assert isinstance(spec, SourceSpec)
    assert spec.derived_name == "skills"


def test_parse_returns_none_for_empty() -> None:
    assert parse_source_spec("") is None
    assert parse_source_spec("   ") is None


def test_parse_uses_custom_ref() -> None:
    spec = parse_source_spec("anthropics/skills", ref="v1.0.0")
    assert spec is not None
    assert spec.ref == "v1.0.0"


def test_parse_local_expands_user() -> None:
    spec = parse_source_spec("~/my-skills")
    assert spec is not None
    assert spec.kind == "local"
    assert "~" not in spec.url_or_path  # expanduser ran


@pytest.mark.parametrize(
    ("text", "expected_url", "expected_ref", "expected_subpath", "expected_name"),
    [
        # GitHub /tree/<ref>/<subpath>
        (
            "https://github.com/vercel-labs/agent-skills/tree/main/skills/web-design-guidelines",
            "https://github.com/vercel-labs/agent-skills",
            "main",
            "skills/web-design-guidelines",
            "web-design-guidelines",
        ),
        # multi-segment subpath
        (
            "https://github.com/owner/repo/tree/develop/a/b/c",
            "https://github.com/owner/repo",
            "develop",
            "a/b/c",
            "c",
        ),
        # GitLab /-/tree/
        (
            "https://gitlab.com/org/repo/-/tree/main/skills/foo",
            "https://gitlab.com/org/repo",
            "main",
            "skills/foo",
            "foo",
        ),
        # /tree/<ref> only — subpath is None, name falls back to repo
        (
            "https://github.com/owner/repo/tree/feature-branch",
            "https://github.com/owner/repo",
            "feature-branch",
            None,
            "repo",
        ),
        # trailing slash stripped
        (
            "https://github.com/owner/repo/tree/main/skills/foo/",
            "https://github.com/owner/repo",
            "main",
            "skills/foo",
            "foo",
        ),
        # .git suffix stripped from base URL
        (
            "https://github.com/owner/repo.git/tree/main/skills/foo",
            "https://github.com/owner/repo",
            "main",
            "skills/foo",
            "foo",
        ),
    ],
)
def test_parse_deep_tree_url(
    text: str,
    expected_url: str,
    expected_ref: str,
    expected_subpath: str | None,
    expected_name: str,
) -> None:
    spec = parse_source_spec(text)
    assert spec is not None, f"expected SourceSpec for {text!r}"
    assert spec.kind == "git"
    assert spec.url_or_path == expected_url
    assert spec.ref == expected_ref
    assert spec.subpath == expected_subpath
    assert spec.derived_name == expected_name


def test_deep_tree_url_explicit_ref_overrides_tree_ref() -> None:
    """--ref overrides the ref embedded in a tree URL."""
    spec = parse_source_spec(
        "https://github.com/owner/repo/tree/main/skills/foo",
        ref="v2.0.0",
    )
    assert spec is not None
    assert spec.ref == "v2.0.0"
    assert spec.subpath == "skills/foo"


def test_plain_https_url_has_no_subpath() -> None:
    """A plain https:// URL without /tree/ must not get a subpath."""
    spec = parse_source_spec("https://github.com/anthropics/skills")
    assert spec is not None
    assert spec.subpath is None
    assert spec.ref is None


def test_derive_unique_name_no_collision() -> None:
    assert derive_unique_name("foo", set()) == "foo"
    assert derive_unique_name("foo", {"bar"}) == "foo"


def test_derive_unique_name_increments_on_collision() -> None:
    assert derive_unique_name("foo", {"foo"}) == "foo-2"
    assert derive_unique_name("foo", {"foo", "foo-2"}) == "foo-3"
    assert derive_unique_name("foo", {"foo", "foo-2", "foo-3", "foo-4"}) == "foo-5"
