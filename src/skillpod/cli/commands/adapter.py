"""`skillpod adapter list` — enumerate the active adapter registry.

Prints one row per agent declared in the manifest:

    agent | adapter | mode-supported

Custom adapters are imported and instantiated here so that import errors
surface in the same way they do during ``skillpod install``.
"""

from __future__ import annotations

from pathlib import Path

from skillpod.cli._output import emit, fail, run_with_exit_codes
from skillpod.installer.adapter_registry import get_adapter, reset_registry
from skillpod.installer.pipeline import _register_manifest_adapters
from skillpod.manifest import load as load_manifest


def _modes_supported(adapter: object) -> str:
    """Return the mode-supported string for an adapter instance.

    ``IdentityAdapter`` exposes a ``modes_supported`` property; custom
    adapters may override it.  Fall back to listing all three modes for
    any adapter that does not provide the property.
    """
    prop = getattr(adapter, "modes_supported", None)
    if callable(prop):
        result = prop()
        return str(result)
    if isinstance(prop, str):
        return prop
    return "symlink, copy, hardlink"


def _adapter_dotted_path(adapter: object) -> str:
    """Return the fully-qualified dotted path of an adapter instance."""
    cls = type(adapter)
    return f"{cls.__module__}.{cls.__qualname__}"


def _list_impl(project_root: Path, manifest_path: Path) -> list[dict[str, str]]:
    manifest = load_manifest(manifest_path)

    # Re-register adapters so import errors surface here too.
    reset_registry()
    _register_manifest_adapters(manifest.agents)

    rows: list[dict[str, str]] = []
    for entry in manifest.agents:
        adapter = get_adapter(entry.name)
        rows.append(
            {
                "agent": entry.name,
                "adapter": _adapter_dotted_path(adapter),
                "mode-supported": _modes_supported(adapter),
            }
        )
    return rows


def run(*, project_root: Path, manifest_path: Path, json_output: bool) -> None:
    if not manifest_path.exists():
        raise fail(f"{manifest_path} not found", code=1, json_output=json_output)

    rows = run_with_exit_codes(
        lambda: _list_impl(project_root, manifest_path),
        json_output=json_output,
    )
    payload = {"ok": True, "adapters": rows}

    if json_output:
        emit(payload, json_output=True)
        return

    if not rows:
        emit(payload, json_output=False, human="No agents declared.")
        return

    agent_w = max(5, *(len(r["agent"]) for r in rows))
    adapter_w = max(7, *(len(r["adapter"]) for r in rows))
    header = f"{'AGENT':<{agent_w}}  {'ADAPTER':<{adapter_w}}  MODE-SUPPORTED"
    lines = [header]
    for r in rows:
        lines.append(
            f"{r['agent']:<{agent_w}}  {r['adapter']:<{adapter_w}}  {r['mode-supported']}"
        )
    emit(payload, json_output=False, human="\n".join(lines))


__all__ = ["run"]
