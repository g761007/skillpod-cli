"""skills.sh client.

skills.sh is treated as a *discovery* layer only — it answers "given the
skill name `audit`, which git repo and commit should I install?" and
nothing more.

We do not own the registry, so the JSON contract here is intentionally
small and tolerant of extra keys. The minimal shape we require for a
single-skill lookup ``GET <base>/api/skills/<name>`` is::

    {
      "name": "audit",
      "repo": {
        "host": "github.com",
        "org":  "vercel-labs",
        "name": "agent-skills",
        "url":  "https://github.com/vercel-labs/agent-skills"
      },
      "ref":    "main",
      "commit": "<40-char-sha>",
      "meta":   { "verified": true, "installs": 1234, "stars": 56 }
    }

`meta` is optional in 0.1.0 (used only for trust policy in 0.2.0).

The base URL is configurable via the environment variable
``SKILLPOD_REGISTRY_URL`` so tests can mock it with respx.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import httpx

from skillpod.registry.errors import (
    RegistryError,
    RegistryMalformed,
    RegistryNotFound,
    RegistryUnavailable,
)

DEFAULT_BASE_URL = "https://skills.sh"


def _base_url() -> str:
    return os.environ.get("SKILLPOD_REGISTRY_URL", DEFAULT_BASE_URL).rstrip("/")


@dataclass(frozen=True)
class RepoInfo:
    """Minimal payload returned by a registry lookup.

    Trust signals (`verified`, `installs`, `stars`) are populated from the
    registry's `meta` dict (Roadmap 0.2.0, `add-skillpod-trust-and-search`
    §2.1). Defaults preserve backwards-compat with payloads that omit `meta`.
    """

    name: str
    host: str
    org: str
    repo: str
    url: str
    ref: str
    commit: str
    meta: dict[str, Any] = field(default_factory=dict)
    verified: bool = False
    installs: int = 0
    stars: int = 0


def _require(d: dict[str, Any], path: str) -> Any:
    """Look up a dotted-path key; raise RegistryMalformed on miss."""
    cursor: Any = d
    for part in path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            raise RegistryMalformed(f"registry response missing field {path!r}")
        cursor = cursor[part]
    return cursor


def _parse_payload(name: str, payload: dict[str, Any]) -> RepoInfo:
    repo = _require(payload, "repo")
    if not isinstance(repo, dict):
        raise RegistryMalformed("registry response: `repo` is not an object")

    meta: dict[str, Any] = dict(payload.get("meta") or {})

    info = RepoInfo(
        name=name,
        host=str(_require(payload, "repo.host")),
        org=str(_require(payload, "repo.org")),
        repo=str(_require(payload, "repo.name")),
        url=str(_require(payload, "repo.url")),
        ref=str(_require(payload, "ref")),
        commit=str(_require(payload, "commit")),
        meta=meta,
        verified=bool(meta.get("verified", False)),
        installs=int(meta.get("installs", 0)),
        stars=int(meta.get("stars", 0)),
    )

    if len(info.commit) != 40 or any(ch not in "0123456789abcdef" for ch in info.commit):
        raise RegistryMalformed(
            f"registry returned non-canonical commit for {name!r}: {info.commit!r}"
        )
    return info


def lookup(name: str, *, client: httpx.Client | None = None) -> RepoInfo:
    """Resolve `name` against skills.sh and return the parsed `RepoInfo`."""
    url = f"{_base_url()}/api/skills/{name}"
    own_client = client is None
    http = client or httpx.Client(timeout=httpx.Timeout(10.0))
    try:
        try:
            resp = http.get(url)
        except httpx.RequestError as exc:
            raise RegistryUnavailable(f"registry request to {url} failed: {exc}") from exc

        if resp.status_code == 404:
            raise RegistryNotFound(f"registry has no entry for skill {name!r}")
        if resp.status_code >= 400:
            raise RegistryUnavailable(
                f"registry returned HTTP {resp.status_code} for {url}"
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise RegistryMalformed(f"registry response was not JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise RegistryMalformed("registry response: top level is not an object")

        return _parse_payload(name, data)
    finally:
        if own_client:
            http.close()


__all__ = [
    "DEFAULT_BASE_URL",
    "RegistryError",
    "RegistryMalformed",
    "RegistryNotFound",
    "RegistryUnavailable",
    "RepoInfo",
    "lookup",
]
