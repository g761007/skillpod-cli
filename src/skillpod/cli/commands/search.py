"""`skillpod search <query>` — query the registry and display results.

Backed by skills.sh's public ``/api/search?q=<query>&limit=<n>`` endpoint
(see :func:`skillpod.registry.search`).  Results are fuzzy and may include
multiple skills; ``--limit`` caps how many rows are displayed.

The search API does not expose ``verified`` or ``stars`` — those columns
render as ``-``, and ``passes-policy`` is computed from the signals that
*are* available (``installs`` threshold and ``allow_unverified``).  For
strict pinned-commit installs use ``skillpod add``, which goes through
the per-skill detail surface in :func:`skillpod.registry.lookup`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from skillpod.cli._output import emit, fail
from skillpod.manifest import load as load_manifest
from skillpod.manifest.models import RegistrySkillsShPolicy
from skillpod.registry import (
    RegistryError,
    SearchHit,
    search,
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

    try:
        hits = search(query, limit=limit)
    except RegistryError as exc:
        raise fail(str(exc), code=2, json_output=json_output) from exc

    rows = [_row_for_hit(hit, policy) for hit in hits[:limit]]
    _render(query, rows, json_output=json_output)


def _row_for_hit(
    hit: SearchHit, policy: RegistrySkillsShPolicy
) -> dict[str, Any]:
    # The public search API does not expose `verified` or `stars`, so we
    # cannot enforce those thresholds — pass only when `allow_unverified`
    # is on AND the installs threshold is met.
    passes_policy = policy.allow_unverified and hit.installs >= policy.min_installs
    return {
        "name": hit.name,
        "repo": hit.url,
        "source": hit.source,
        "installs": hit.installs,
        "stars": None,
        "verified": None,
        "passes_policy": passes_policy,
    }


def _render(query: str, results: list[dict[str, Any]], *, json_output: bool) -> None:
    payload = {"query": query, "results": results}
    if json_output:
        emit(payload, json_output=True)
        return

    if not results:
        emit(payload, json_output=False, human=f"No results for {query!r}.")
        return

    col_headers = ["name", "repo", "installs", "stars", "verified", "passes-policy"]
    rows_display = [
        [
            r["name"],
            r["repo"],
            str(r["installs"]),
            "-" if r["stars"] is None else str(r["stars"]),
            "-" if r["verified"] is None else str(r["verified"]).lower(),
            str(r["passes_policy"]).lower(),
        ]
        for r in results
    ]

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
