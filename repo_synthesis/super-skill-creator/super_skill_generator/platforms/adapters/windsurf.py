"""Windsurf adapter — converts SKILL.md to Windsurf format."""

from __future__ import annotations

import shutil
from pathlib import Path

from .base import PlatformAdapter


class WindsurfAdapter(PlatformAdapter):
    @property
    def name(self) -> str:
        return "windsurf"

    def get_install_dir(self) -> Path:
        return Path.home() / ".windsurf" / "rules"

    def install(self, skill_path: Path) -> Path:
        dest = self.get_install_dir()
        dest.mkdir(parents=True, exist_ok=True)
        if skill_path.is_dir():
            skill_md = skill_path / "SKILL.md"
            if not skill_md.exists():
                raise FileNotFoundError("No SKILL.md found")
            target = dest / f"{skill_path.name}.md"
            shutil.copy2(skill_md, target)
            return target
        else:
            target = dest / skill_path.name
            shutil.copy2(skill_path, target)
            return target
