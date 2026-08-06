"""Native SKILL.md adapter — works for 10+ platforms."""

from __future__ import annotations

from pathlib import Path

from .base import PlatformAdapter, install_file, install_tree

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

    def install(self, skill_path: Path, *, force: bool = False, dry_run: bool = True) -> Path:
        dest = self.get_install_dir()
        if skill_path.is_dir():
            target = dest / skill_path.name
            return install_tree(skill_path, target, force=force, dry_run=dry_run)
        else:
            target = dest / skill_path.name
            return install_file(skill_path, target, force=force, dry_run=dry_run)
