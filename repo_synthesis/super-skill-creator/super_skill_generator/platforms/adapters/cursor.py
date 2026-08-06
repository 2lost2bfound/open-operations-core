"""Cursor adapter — converts SKILL.md to .mdc format."""

from __future__ import annotations

import shutil
from pathlib import Path

from .base import PlatformAdapter


class CursorAdapter(PlatformAdapter):
    @property
    def name(self) -> str:
        return "cursor"

    def get_install_dir(self) -> Path:
        return Path.home() / ".cursor" / "rules"

    def install(self, skill_path: Path) -> Path:
        dest = self.get_install_dir()
        dest.mkdir(parents=True, exist_ok=True)
        if skill_path.is_dir():
            skill_md = skill_path / "SKILL.md"
            if not skill_md.exists():
                raise FileNotFoundError("No SKILL.md found")
            content = skill_md.read_text(encoding="utf-8")
            mdc_content = self._convert_to_mdc(content)
            target = dest / f"{skill_path.name}.mdc"
            target.write_text(mdc_content, encoding="utf-8")
            return target
        else:
            content = skill_path.read_text(encoding="utf-8")
            mdc_content = self._convert_to_mdc(content)
            target = dest / f"{skill_path.stem}.mdc"
            target.write_text(mdc_content, encoding="utf-8")
            return target

    def _convert_to_mdc(self, content: str) -> str:
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                fm = content[3:end].strip()
                body = content[end + 3:].strip()
                return f"---\n{fm}\nglobs:\nalwaysApply: false\n---\n{body}"
        return content
