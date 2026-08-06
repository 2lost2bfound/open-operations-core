"""Native SKILL.md adapter — works for 10+ platforms."""

from __future__ import annotations

import shutil
from pathlib import Path

from .base import PlatformAdapter

PLATFORM_DIRS = {
    "claude-code": ".claude/skills",
    "codex": ".codex/skills",
    "opencode": ".config/opencode/skills",
    "cline": ".cline/skills",
    "aider": ".aider/skills",
    "copilot": ".github/copilot/skills",
    "trae": ".trae/skills",
    "kiro": ".kiro/skills",
    "amp": ".amp/skills",
    "goose": ".goose/skills",
}


class NativeAdapter(PlatformAdapter):
    def __init__(self, platform: str) -> None:
        self._platform = platform

    @property
    def name(self) -> str:
        return self._platform

    def get_install_dir(self) -> Path:
        rel = PLATFORM_DIRS.get(self._platform, f".{self._platform}/skills")
        return Path.home() / rel

    def install(self, skill_path: Path) -> Path:
        dest = self.get_install_dir()
        dest.mkdir(parents=True, exist_ok=True)
        if skill_path.is_dir():
            target = dest / skill_path.name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(skill_path, target)
            return target
        else:
            target = dest / skill_path.name
            shutil.copy2(skill_path, target)
            return target
