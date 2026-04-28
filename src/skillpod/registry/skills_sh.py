"""skills.sh client.

skills.sh is treated as a *discovery* layer only.  Two surfaces are used:

1. ``GET <base>/api/search?q=<query>&limit=<n>`` — public fuzzy-search API
   used by the ``skillpod search`` command.  Returns a flat list of hits::

       {"query": "...", "skills": [
           {"id": "owner/repo/skillId", "skillId": "...", "name": "...",
            "installs": N, "source": "owner/repo"},
           ...
       ], "count": N}

   No git coordinates (ref/commit) and no trust signals (verified/stars)
   are exposed here — only ``installs``.

2. ``GET <base>/api/skills/<name>`` — *historical* per-skill detail
   contract used by the install pipeline (``installer/resolve.py``).  The
   public skills.sh deployment does NOT serve this path (it 404s — the
   path is a Next.js web-UI route).  ``lookup()`` is preserved against
   this contract so it can talk to a future per-skill detail API or a
   self-hosted registry mirror.  The expected shape is::

       {
         "name": "audit",
         "repo": {"host": "github.com", "org": "...", "name": "...",
                  "url": "https://github.com/.../..."},
         "ref": "main",
         "commit": "<40-char-sha>",
         "meta": {"verified": true, "installs": 1234, "stars": 56}
       }

The base URL is configurable via the environment variable
``SKILLPOD_REGISTRY_URL`` so tests can mock both endpoints with respx.

See ``.omc/research/skills-sh-probe.md`` for the original probe of the
public skills.sh API.
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


@dataclass(frozen=True)
class SearchHit:
    """One row from the public ``/api/search`` endpoint.

    The public search API exposes only a small subset of what ``RepoInfo``
    can carry.  Notably, ``ref``/``commit`` (git coordinates) and
    ``verified``/``stars`` (trust signals) are NOT available — the search
    surface is a discovery aid, not an install target.
    """

    name: str
    skill_id: str
    full_id: str
    source: str
    installs: int
    url: str


def _parse_search_hit(raw: dict[str, Any]) -> SearchHit:
    name = str(_require(raw, "name"))
    skill_id = str(_require(raw, "skillId"))
    full_id = str(_require(raw, "id"))
    source = str(_require(raw, "source"))
    installs = int(raw.get("installs", 0) or 0)
    url = f"https://github.com/{source}" if "/" in source else source
    return SearchHit(
        name=name,
        skill_id=skill_id,
        full_id=full_id,
        source=source,
        installs=installs,
        url=url,
    )


def search(
    query: str,
    *,
    limit: int = 20,
    client: httpx.Client | None = None,
) -> list[SearchHit]:
    """Query the public ``/api/search`` endpoint on skills.sh.

    Returns a list of :class:`SearchHit` objects (possibly empty).  Raises
    :class:`RegistryUnavailable` for transport/HTTP errors and
    :class:`RegistryMalformed` if the JSON shape does not match the
    documented contract.

    Note: search is fuzzy and may return rows whose ``name`` does not
    equal *query*; the caller decides how to filter or rank results.
    """
    if limit < 1:
        limit = 1
    url = f"{_base_url()}/api/search"
    params: dict[str, str] = {"q": query, "limit": str(limit)}
    own_client = client is None
    http = client or httpx.Client(timeout=httpx.Timeout(10.0))
    try:
        try:
            resp = http.get(url, params=params)
        except httpx.RequestError as exc:
            raise RegistryUnavailable(f"registry request to {url} failed: {exc}") from exc

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

        skills = data.get("skills", [])
        if not isinstance(skills, list):
            raise RegistryMalformed("registry response: `skills` is not a list")

        hits: list[SearchHit] = []
        for raw in skills:
            if not isinstance(raw, dict):
                raise RegistryMalformed("registry response: skill entry is not an object")
            hits.append(_parse_search_hit(raw))
        return hits
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
    "SearchHit",
    "lookup",
    "search",
]
