"""`skillpod search <query>` — query the registry and display results.

MVP limitation: there is no list/search endpoint on skills.sh yet, so this
command treats ``<query>`` as an exact skill name and calls ``registry.lookup``
once, returning at most one row.  A richer full-text search endpoint (and the
``--limit`` cap it implies) will be wired in a future change once the registry
exposes it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skillpod.cli._output import emit, fail
from skillpod.manifest import load as load_manifest
from skillpod.manifest.models import RegistrySkillsShPolicy
from skillpod.registry import (
    RegistryError,
    RegistryNotFound,
    TrustError,
    enforce,
    lookup,
)


def run(
    *,
    project_root: Path,
    manifest_path: Path,
    query: str,
    limit: int,
    json_output: bool,
) -> None:
    # Load trust policy from manifest if it exists; otherwise use defaults so
    # `search` works in fresh checkouts without a manifest.
    if manifest_path.exists():
        try:
            manifest = load_manifest(manifest_path)
            policy = manifest.registry.skills_sh
        except Exception:
            policy = RegistrySkillsShPolicy()
    else:
        policy = RegistrySkillsShPolicy()

    # Perform lookup — treat query as exact skill name (MVP, see module docstring).
    try:
        info = lookup(query)
    except RegistryNotFound:
        # Zero results is not an error.
        _render(query, [], json_output=json_output)
        return
    except RegistryError as exc:
        raise fail(str(exc), code=2, json_output=json_output) from exc

    # Evaluate trust policy — do NOT abort; just record the verdict.
    try:
        enforce(policy, info)
        passes_policy = True
    except TrustError:
        passes_policy = False

    row = {
        "name": info.name,
        "repo": info.url,
        "installs": info.installs,
        "stars": info.stars,
        "verified": info.verified,
        "passes_policy": passes_policy,
    }
    results = [row][:limit]
    _render(query, results, json_output=json_output)


def _render(query: str, results: list[dict[str, Any]], *, json_output: bool) -> None:
    payload = {"query": query, "results": results}
    if json_output:
        emit(payload, json_output=True)
        return

    if not results:
        emit(payload, json_output=False, human=f"No results for {query!r}.")
        return

    # Column order: name | repo | installs | stars | verified | passes-policy
    col_headers = ["name", "repo", "installs", "stars", "verified", "passes-policy"]
    rows_display = [
        [
            r["name"],
            r["repo"],
            str(r["installs"]),
            str(r["stars"]),
            str(r["verified"]).lower(),
            str(r["passes_policy"]).lower(),
        ]
        for r in results
    ]

    # Compute column widths.
    widths = [len(h) for h in col_headers]
    for row in rows_display:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def _fmt(cells: list[str]) -> str:
        return "  ".join(c.ljust(widths[i]) for i, c in enumerate(cells))

    lines = [_fmt(col_headers)]
    lines.append("  ".join("-" * w for w in widths))
    for row in rows_display:
        lines.append(_fmt(row))

    emit(payload, json_output=False, human="\n".join(lines))


__all__ = ["run"]
