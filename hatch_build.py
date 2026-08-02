"""Stamp the build commit into the wheel.

The release version moves rarely, so it cannot distinguish two builds. `uv tool install`
copies the source, meaning an install silently goes stale as soon as the branch advances
— and with no build marker the only way to tell was to inspect package internals.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class BuildInfoHook(BuildHookInterface):
    PLUGIN_NAME = "build-info"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        commit = "unknown"
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                commit = result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            # Building from an sdist has no git; "unknown" is a valid answer here
            # because the sdist already carries a stamp, preserved below.
            pass

        target = Path(self.root) / "src" / "wherewolf" / "_build_info.py"

        if commit == "unknown" and target.is_file():
            # `uv build` builds the sdist first, then builds the wheel *from* the
            # extracted sdist, where no git repository exists. The sdist already carries
            # a real stamp, so keep it rather than overwriting it with "unknown".
            existing = target.read_text(encoding="utf-8")
            if 'COMMIT = "unknown"' not in existing:
                return

        target.write_text(
            '"""Generated at build time by hatch_build.py. Do not edit."""\n\n'
            f'COMMIT = "{commit}"\n',
            encoding="utf-8",
        )
