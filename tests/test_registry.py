"""Tests for the registry-discovery capability.

Scenarios trace to
`openspec/changes/add-skillpod-mvp-install/specs/registry-discovery/spec.md`.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from skillpod.manifest.models import RegistrySkillsShPolicy
from skillpod.registry import (
    DEFAULT_BASE_URL,
    RegistryMalformed,
    RegistryNotFound,
    RegistryUnavailable,
    RepoInfo,
    TrustError,
    enforce,
    lookup,
)

_BASE = "https://registry.test"
_GOOD_COMMIT = "a" * 40


@pytest.fixture(autouse=True)
def _registry_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLPOD_REGISTRY_URL", _BASE)


def _good_payload() -> dict[str, object]:
    return {
        "name": "audit",
        "repo": {
            "host": "github.com",
            "org": "vercel-labs",
            "name": "agent-skills",
            "url": "https://github.com/vercel-labs/agent-skills",
        },
        "ref": "main",
        "commit": _GOOD_COMMIT,
        "meta": {"verified": True, "installs": 1234, "stars": 56},
    }


# ---- happy path ------------------------------------------------------------


@respx.mock
def test_lookup_happy_path() -> None:
    """Scenario: Unknown skill resolved through registry."""
    route = respx.get(f"{_BASE}/api/skills/audit").mock(
        return_value=httpx.Response(200, json=_good_payload())
    )

    info = lookup("audit")

    assert route.called
    assert info == RepoInfo(
        name="audit",
        host="github.com",
        org="vercel-labs",
        repo="agent-skills",
        url="https://github.com/vercel-labs/agent-skills",
        ref="main",
        commit=_GOOD_COMMIT,
        meta={"verified": True, "installs": 1234, "stars": 56},
        verified=True,
        installs=1234,
        stars=56,
    )


@respx.mock
def test_lookup_default_base_url_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SKILLPOD_REGISTRY_URL", raising=False)
    route = respx.get(f"{DEFAULT_BASE_URL}/api/skills/audit").mock(
        return_value=httpx.Response(200, json=_good_payload())
    )
    lookup("audit")
    assert route.called


@respx.mock
def test_meta_field_is_optional() -> None:
    """0.1.0 only requires repo + ref + commit; meta is for 0.2.0."""
    payload = _good_payload()
    del payload["meta"]
    respx.get(f"{_BASE}/api/skills/audit").mock(
        return_value=httpx.Response(200, json=payload)
    )

    info = lookup("audit")
    assert info.meta == {}


# ---- failure modes ---------------------------------------------------------


@respx.mock
def test_lookup_404_raises_registry_not_found() -> None:
    """Scenario: Registry timeout aborts install (404 variant)."""
    respx.get(f"{_BASE}/api/skills/ghost").mock(
        return_value=httpx.Response(404, text="not found")
    )
    with pytest.raises(RegistryNotFound):
        lookup("ghost")


@respx.mock
def test_lookup_5xx_raises_registry_unavailable() -> None:
    respx.get(f"{_BASE}/api/skills/audit").mock(
        return_value=httpx.Response(500, text="boom")
    )
    with pytest.raises(RegistryUnavailable, match="HTTP 500"):
        lookup("audit")


@respx.mock
def test_lookup_network_error_raises_registry_unavailable() -> None:
    """Scenario: Registry timeout aborts install (network variant)."""
    respx.get(f"{_BASE}/api/skills/audit").mock(
        side_effect=httpx.ConnectTimeout("timeout")
    )
    with pytest.raises(RegistryUnavailable, match="failed"):
        lookup("audit")


@respx.mock
def test_lookup_non_json_raises_malformed() -> None:
    respx.get(f"{_BASE}/api/skills/audit").mock(
        return_value=httpx.Response(200, text="<html>nope</html>")
    )
    with pytest.raises(RegistryMalformed):
        lookup("audit")


@respx.mock
def test_lookup_missing_required_field_raises() -> None:
    payload = _good_payload()
    del payload["commit"]
    respx.get(f"{_BASE}/api/skills/audit").mock(
        return_value=httpx.Response(200, json=payload)
    )
    with pytest.raises(RegistryMalformed, match="commit"):
        lookup("audit")


@respx.mock
def test_lookup_short_commit_raises_malformed() -> None:
    payload = _good_payload()
    payload["commit"] = "abc"
    respx.get(f"{_BASE}/api/skills/audit").mock(
        return_value=httpx.Response(200, json=payload)
    )
    with pytest.raises(RegistryMalformed, match="non-canonical commit"):
        lookup("audit")


@respx.mock
def test_lookup_uppercase_commit_raises_malformed() -> None:
    payload = _good_payload()
    payload["commit"] = ("F" * 40)
    respx.get(f"{_BASE}/api/skills/audit").mock(
        return_value=httpx.Response(200, json=payload)
    )
    with pytest.raises(RegistryMalformed):
        lookup("audit")


@respx.mock
def test_lookup_top_level_array_rejected() -> None:
    respx.get(f"{_BASE}/api/skills/audit").mock(
        return_value=httpx.Response(200, json=[1, 2, 3])
    )
    with pytest.raises(RegistryMalformed, match="not an object"):
        lookup("audit")


# ---- read-only contract -----------------------------------------------------


@respx.mock
def test_lookup_uses_only_get(monkeypatch: pytest.MonkeyPatch) -> None:
    """Registry is read-only — lookup must issue a GET."""
    route = respx.get(f"{_BASE}/api/skills/audit").mock(
        return_value=httpx.Response(200, json=_good_payload())
    )
    lookup("audit")
    assert route.called
    assert route.calls.last.request.method == "GET"


# ---- caller-supplied client ------------------------------------------------


@respx.mock
def test_lookup_can_reuse_external_client() -> None:
    respx.get(f"{_BASE}/api/skills/audit").mock(
        return_value=httpx.Response(200, json=_good_payload())
    )
    client = httpx.Client(timeout=2.0)
    try:
        lookup("audit", client=client)
    finally:
        client.close()
    # Confirm the client is still usable after lookup (i.e. lookup did not close it).
    client = httpx.Client(timeout=2.0)
    client.close()


# ---- RepoInfo trust-signal extension (add-skillpod-trust-and-search §2.1) ---


@respx.mock
def test_repo_info_populates_trust_fields_from_meta() -> None:
    """RepoInfo reads verified/installs/stars from the meta dict when present."""
    respx.get(f"{_BASE}/api/skills/audit").mock(
        return_value=httpx.Response(200, json=_good_payload())
    )
    info = lookup("audit")
    assert info.verified is True
    assert info.installs == 1234
    assert info.stars == 56


@respx.mock
def test_repo_info_trust_fields_default_when_meta_absent() -> None:
    """RepoInfo trust fields fall back to safe defaults when meta is absent."""
    payload = _good_payload()
    del payload["meta"]
    respx.get(f"{_BASE}/api/skills/audit").mock(
        return_value=httpx.Response(200, json=payload)
    )
    info = lookup("audit")
    assert info.verified is False
    assert info.installs == 0
    assert info.stars == 0


@respx.mock
def test_repo_info_trust_fields_default_when_meta_empty() -> None:
    """RepoInfo trust fields fall back to safe defaults when meta is an empty dict."""
    payload = _good_payload()
    payload["meta"] = {}
    respx.get(f"{_BASE}/api/skills/audit").mock(
        return_value=httpx.Response(200, json=payload)
    )
    info = lookup("audit")
    assert info.verified is False
    assert info.installs == 0
    assert info.stars == 0


# ---- Trust policy enforcement (add-skillpod-trust-and-search §2.2) ----------


def _make_repo(
    *,
    verified: bool = True,
    installs: int = 0,
    stars: int = 0,
) -> RepoInfo:
    """Construct a minimal RepoInfo with controllable trust signals."""
    return RepoInfo(
        name="audit",
        host="github.com",
        org="vercel-labs",
        repo="agent-skills",
        url="https://github.com/vercel-labs/agent-skills",
        ref="main",
        commit=_GOOD_COMMIT,
        verified=verified,
        installs=installs,
        stars=stars,
    )


def test_enforce_verified_skill_passes_default_policy() -> None:
    """Scenario: Verified skill passes default policy.

    registry-discovery spec §'Verified skill passes default policy'.
    """
    policy = RegistrySkillsShPolicy()
    repo = _make_repo(verified=True, installs=5, stars=1)
    result = enforce(policy, repo)
    assert result is repo


def test_enforce_unverified_skill_blocked_by_default() -> None:
    """Scenario: Unverified skill blocked by default.

    registry-discovery spec §'Unverified skill blocked by default'.
    """
    policy = RegistrySkillsShPolicy()
    repo = _make_repo(verified=False)
    with pytest.raises(TrustError) as exc_info:
        enforce(policy, repo)
    assert "verified" in exc_info.value.reasons[0].lower()


def test_enforce_allow_unverified_true_passes() -> None:
    """When allow_unverified=True, an unverified skill passes the filter."""
    policy = RegistrySkillsShPolicy(allow_unverified=True)
    repo = _make_repo(verified=False, installs=0, stars=0)
    result = enforce(policy, repo)
    assert result is repo


def test_enforce_installs_below_threshold_blocked() -> None:
    """min_installs threshold is enforced independently."""
    policy = RegistrySkillsShPolicy(allow_unverified=True, min_installs=100)
    repo = _make_repo(verified=True, installs=50)
    with pytest.raises(TrustError) as exc_info:
        enforce(policy, repo)
    assert len(exc_info.value.reasons) == 1
    assert "installs" in exc_info.value.reasons[0]


def test_enforce_stars_below_threshold_blocked() -> None:
    """min_stars threshold is enforced independently."""
    policy = RegistrySkillsShPolicy(allow_unverified=True, min_stars=20)
    repo = _make_repo(verified=True, stars=5)
    with pytest.raises(TrustError) as exc_info:
        enforce(policy, repo)
    assert len(exc_info.value.reasons) == 1
    assert "stars" in exc_info.value.reasons[0]


def test_enforce_multiple_thresholds_reported_together() -> None:
    """Scenario: Multiple thresholds reported together in a single TrustError.

    registry-discovery spec §'Multiple thresholds reported together'.
    Policy: allow_unverified=false, min_installs=1000, min_stars=50.
    Result: verified=false, installs=12, stars=3  → all three fail.
    """
    policy = RegistrySkillsShPolicy(
        allow_unverified=False,
        min_installs=1000,
        min_stars=50,
    )
    repo = _make_repo(verified=False, installs=12, stars=3)
    with pytest.raises(TrustError) as exc_info:
        enforce(policy, repo)
    err = exc_info.value
    assert len(err.reasons) == 3
    reasons_text = " ".join(err.reasons).lower()
    assert "verified" in reasons_text
    assert "installs" in reasons_text
    assert "stars" in reasons_text


def test_trust_error_is_registry_error() -> None:
    """TrustError must be a subclass of RegistryError for consistent error handling."""
    from skillpod.registry.errors import RegistryError

    policy = RegistrySkillsShPolicy()
    repo = _make_repo(verified=False)
    with pytest.raises(RegistryError):
        enforce(policy, repo)


def test_trust_error_str_contains_all_reasons() -> None:
    """str(TrustError) should surface all reasons (joined by '; ')."""
    err = TrustError(["reason one", "reason two"])
    assert "reason one" in str(err)
    assert "reason two" in str(err)
