"""Windsurf adapter — converts SKILL.md to Windsurf format."""

from __future__ import annotations

from pathlib import Path

from .base import PlatformAdapter, install_file


class WindsurfAdapter(PlatformAdapter):
    @property
    def name(self) -> str:
        return "windsurf"

    def get_install_dir(self) -> Path:
        return Path.home() / ".windsurf" / "rules"

    def install(self, skill_path: Path, *, force: bool = False, dry_run: bool = True) -> Path:
        dest = self.get_install_dir()
        if skill_path.is_dir():
            skill_md = skill_path / "SKILL.md"
            if not skill_md.exists():
                raise FileNotFoundError("No SKILL.md found")
            target = dest / f"{skill_path.name}.md"
        else:
            target = dest / skill_path.name
            skill_md = skill_path
        return install_file(skill_md, target, force=force, dry_run=dry_run)
