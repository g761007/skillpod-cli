"""Resolve a global-profile target that may be a name or a remote URL.

A bare name (``developer``) is looked up locally. A remote reference downloads
the profile file to ``~/.skillpod/profiles/<name>.yml`` only when it is not
already present (``--update`` forces a refresh). Two remote forms are supported:

- a direct ``https://…/<file>.yml`` URL;
- an ``owner/repo/path/to/<file>.yml`` shorthand, fetched from
  ``raw.githubusercontent.com`` at ``HEAD``.
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import yaml

from skillpod.installer.paths import global_profile_path
from skillpod.profile.errors import ProfileError
from skillpod.profile.io import load_global_profile_body
from skillpod.profile.models import GlobalProfileBody, GlobalProfileFile
from skillpod.profile.snapshot import write_global_profile_body

_BARE_NAME = re.compile(r"^[a-zA-Z0-9_-]+$")


def is_remote_target(target: str) -> bool:
    """True when ``target`` is a remote profile reference rather than a name."""
    return not _BARE_NAME.match(target)


def _resolve_url(target: str) -> str:
    if target.startswith(("http://", "https://")):
        return target
    if target.endswith(".yml") and target.count("/") >= 2:
        owner, repo, *rest = target.split("/")
        path = "/".join(rest)
        return f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}"
    raise ProfileError(
        f"unrecognised profile reference {target!r}; expected a profile name, an "
        "https://…/<file>.yml URL, or an owner/repo/path/<file>.yml shorthand"
    )


def _basename_name(url: str) -> str:
    stem = url.rstrip("/").rsplit("/", 1)[-1]
    if stem.endswith(".yml"):
        stem = stem[: -len(".yml")]
    if not _BARE_NAME.match(stem):
        raise ProfileError(f"cannot derive a profile name from {url!r}")
    return stem


def _download(url: str) -> GlobalProfileBody:
    try:
        resp = httpx.get(url, timeout=httpx.Timeout(10.0), follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise ProfileError(f"failed to download profile from {url}: {exc}") from exc
    try:
        data = yaml.safe_load(resp.text)
    except yaml.YAMLError as exc:
        raise ProfileError(f"downloaded profile is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ProfileError(f"downloaded profile from {url} is not a mapping")
    try:
        return GlobalProfileFile.model_validate(data).profile
    except Exception as exc:
        raise ProfileError(f"downloaded profile from {url} is invalid: {exc}") from exc


def resolve_profile_target(
    target: str,
    *,
    home: Path | None = None,
    update: bool = False,
) -> tuple[str, GlobalProfileBody]:
    """Return ``(name, body)`` for ``target``, downloading it if remote and absent.

    Raises ProfileError when a local name does not exist or a download fails.
    """
    if not is_remote_target(target):
        body = load_global_profile_body(target, home)
        if body is None:
            raise ProfileError(
                f"global profile '{target}' not found in ~/.skillpod/profiles/"
            )
        return target, body

    url = _resolve_url(target)
    provisional = _basename_name(url)
    existing = global_profile_path(provisional, home)
    if existing.is_file() and not update:
        body = load_global_profile_body(provisional, home)
        if body is not None:
            return provisional, body

    body = _download(url)
    save_name = body.name or provisional
    write_global_profile_body(save_name, body, home)
    return save_name, body


__all__ = ["is_remote_target", "resolve_profile_target"]
