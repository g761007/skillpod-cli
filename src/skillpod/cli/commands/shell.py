"""skillpod shell <profile> — spawn a sub-shell with a profile pre-activated."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from skillpod.cli._output import run_with_exit_codes
from skillpod.manifest.loader import load
from skillpod.profile.errors import ProfileError
from skillpod.skillset.compose import compose_effective_skillset

ENV_DEPTH = "SKILLPOD_SHELL_DEPTH"
ENV_ACTIVE = "SKILLPOD_ACTIVE_PROFILE"


def run(
    profile_name: str,
    *,
    project_root: Path,
    manifest_path: Path,
    json_output: bool,
    home: Path | None = None,
) -> None:
    def _run() -> None:
        # 1. Nest guard
        depth_str = os.environ.get(ENV_DEPTH, "0")
        try:
            depth = int(depth_str)
        except ValueError:
            depth = 0
        if depth > 0:
            raise ProfileError("already inside a skillpod shell; exit first")

        # 2. Validate profile before spawning
        manifest = load(manifest_path)
        compose_effective_skillset(
            manifest,
            project_root,
            profile_name=profile_name,
            home=home,
        )

        # 3. Build child env
        child_env = dict(os.environ)
        child_env[ENV_ACTIVE] = profile_name
        child_env[ENV_DEPTH] = str(depth + 1)

        prefix = f"[skillpod:{profile_name}] "
        existing_ps1 = child_env.get("PS1", "")
        if existing_ps1:
            child_env["PS1"] = prefix + existing_ps1
        else:
            child_env["PS1"] = prefix + "$ "

        existing_prompt = child_env.get("PROMPT", "")
        if existing_prompt:
            child_env["PROMPT"] = prefix + existing_prompt
        else:
            child_env["PROMPT"] = prefix + "$ "

        # 4. Spawn shell (blocking)
        shell = os.environ.get("SHELL", "/bin/sh")
        subprocess.run([shell], env=child_env)

    run_with_exit_codes(_run, json_output=json_output)


__all__ = ["run"]
