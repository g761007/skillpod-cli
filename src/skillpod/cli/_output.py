"""Shared output / exit-code helpers for CLI subcommands.

Exit codes (per `cli/spec.md`):
- 0  success
- 1  user-visible error (manifest invalid, conflicts, frozen drift)
- 2  system / network error (registry unreachable, git failure, OS errors)
"""

from __future__ import annotations

import json as _json
import sys
from collections.abc import Callable
from typing import Any, TypeVar

import typer

from skillpod.installer.errors import InstallSystemError, InstallUserError
from skillpod.lockfile.io import LockfileError
from skillpod.manifest.loader import ManifestError
from skillpod.registry.errors import RegistryError
from skillpod.sources.errors import GitOperationError, SourceError

T = TypeVar("T")


def emit(payload: Any, *, json_output: bool, human: str | None = None) -> None:
    """Print either a JSON document or a human-readable string."""
    if json_output:
        typer.echo(_json.dumps(payload, default=str, sort_keys=True))
    else:
        typer.echo(human if human is not None else str(payload))


def fail(message: str, *, code: int, json_output: bool) -> typer.Exit:
    """Emit an error and return a typer.Exit caller can raise."""
    if json_output:
        typer.echo(_json.dumps({"ok": False, "error": message}), err=True)
    else:
        typer.echo(f"skillpod: error: {message}", err=True)
    return typer.Exit(code=code)


def run_with_exit_codes(
    fn: Callable[[], T],
    *,
    json_output: bool,
) -> T:
    """Translate known exceptions to the documented exit codes."""
    try:
        return fn()
    except (ManifestError, LockfileError, InstallUserError, SourceError) as exc:
        raise fail(str(exc), code=1, json_output=json_output) from exc
    except (
        InstallSystemError,
        RegistryError,
        GitOperationError,
    ) as exc:
        raise fail(str(exc), code=2, json_output=json_output) from exc
    except OSError as exc:
        raise fail(str(exc), code=2, json_output=json_output) from exc
    except Exception as exc:  # pragma: no cover - defensive only
        raise fail(f"unexpected error: {exc}", code=2, json_output=json_output) from exc
    finally:
        sys.stdout.flush()
        sys.stderr.flush()


__all__ = ["emit", "fail", "run_with_exit_codes"]
