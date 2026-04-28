"""`skillpod schema` — print or write the skillfile.yml JSON Schema.

The schema is generated from the pydantic manifest models so editor
integrations can validate the same structure the CLI accepts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skillpod.cli._output import emit
from skillpod.manifest.models import Skillfile

_SCHEMA_URI = "https://json-schema.org/draft/2020-12/schema"
_SCHEMA_ID = "https://github.com/g761007/skillpod-cli/schemas/skillfile.schema.json"
_DESCRIPTION = "JSON Schema for skillfile.yml v1 (skillpod manifest format)."


def run(
    *,
    project_root: Path,
    output: Path | None,
    json_output: bool,
    write: bool,
) -> None:
    schema: dict[str, Any] = Skillfile.model_json_schema()
    schema.update(
        {
            "$schema": _SCHEMA_URI,
            "$id": _SCHEMA_ID,
            "title": "Skillfile",
            "description": _DESCRIPTION,
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
        f"Skillfile JSON Schema (v1) — {len(properties)} top-level properties: "
        f"{', '.join(properties)}.\n"
        "Pass --json for the full schema or --output PATH to write a file."
    )
    emit(schema, json_output=False, human=summary)


__all__ = ["run"]
