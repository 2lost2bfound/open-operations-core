"""Phase 4: Detection — identify environment and platform capabilities."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


class DetectionPhase:
    def __init__(self, config: Any) -> None:
        self.config = config

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        detection = {
            "available_tools": self._detect_tools(),
            "platform_dirs": self._detect_platform_dirs(),
            "python_version": self._detect_python(),
            "existing_skills": self._detect_existing(context["output_dir"]),
        }
        context["artifacts"]["detection"] = detection
        return context

    def _detect_tools(self) -> dict[str, bool]:
        tools = ["git", "python3", "node", "npm", "go", "cargo"]
        return {tool: shutil.which(tool) is not None for tool in tools}

    def _detect_platform_dirs(self) -> dict[str, Path | None]:
        home = Path.home()
        dirs = {
            "claude-code": home / ".claude" / "skills",
            "cursor": home / ".cursor" / "skills",
            "codex": home / ".codex" / "skills",
            "opencode": home / ".config" / "opencode" / "skills",
        }
        return {k: v if v.exists() else None for k, v in dirs.items()}

    def _detect_python(self) -> str:
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}"

    def _detect_existing(self, output_dir: Path) -> list[str]:
        if not output_dir.exists():
            return []
        return [p.name for p in output_dir.iterdir() if p.is_dir()]
