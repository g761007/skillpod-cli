"""`skillpod schema` — print or write a skillpod JSON Schema.

Schemas are generated from the pydantic models so editor integrations can
validate the same structures the CLI accepts. ``--profile`` selects the global
profile file schema (``~/.skillpod/profiles/<name>.yml``); the default is the
``skillfile.yml`` manifest schema.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from skillpod.cli._output import emit
from skillpod.manifest.models import Skillfile
from skillpod.profile.models import GlobalProfileFile

_SCHEMA_URI = "https://json-schema.org/draft/2020-12/schema"
_BASE_ID = "https://github.com/g761007/skillpod-cli/schemas"
# The in-tree copies under src/skillpod/schemas/ are regenerated at release time
# for importlib.resources consumers; runtime generation continues to use
# model_json_schema() as the source of truth.

_SKILLFILE = (
    "skillfile.schema.json",
    "Skillfile",
    "JSON Schema for skillfile.yml v1 (skillpod manifest format).",
)
_PROFILE = (
    "global-profile.schema.json",
    "GlobalProfile",
    "JSON Schema for a skillpod global profile file (~/.skillpod/profiles/<name>.yml).",
)


def run(
    *,
    project_root: Path,
    output: Path | None,
    json_output: bool,
    write: bool,
    profile: bool = False,
) -> None:
    model: type[BaseModel] = GlobalProfileFile if profile else Skillfile
    filename, title, description = _PROFILE if profile else _SKILLFILE

    schema: dict[str, Any] = model.model_json_schema()
    schema.update(
        {
            "$schema": _SCHEMA_URI,
            "$id": f"{_BASE_ID}/{filename}",
            "title": title,
            "description": description,
        }
    )

    if write and output is not None:
        output.write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return

    if json_output:
        emit(schema, json_output=True)
        return

    properties = list(schema.get("properties", {}))
    summary = (
        f"{title} JSON Schema — {len(properties)} top-level properties: "
        f"{', '.join(properties)}.\n"
        "Pass --json for the full schema or --output PATH to write a file."
    )
    emit(schema, json_output=False, human=summary)


__all__ = ["run"]
