"""Cursor adapter — converts SKILL.md to .mdc format."""

from __future__ import annotations

from pathlib import Path

from .base import PlatformAdapter, install_file


class CursorAdapter(PlatformAdapter):
    @property
    def name(self) -> str:
        return "cursor"

    def get_install_dir(self) -> Path:
        return Path.home() / ".cursor" / "rules"

    def install(self, skill_path: Path, *, force: bool = False, dry_run: bool = True) -> Path:
        dest = self.get_install_dir()
        if skill_path.is_dir():
            skill_md = skill_path / "SKILL.md"
            if not skill_md.exists():
                raise FileNotFoundError("No SKILL.md found")
            content = skill_md.read_text(encoding="utf-8")
            mdc_content = self._convert_to_mdc(content)
            target = dest / f"{skill_path.name}.mdc"
        else:
            content = skill_path.read_text(encoding="utf-8")
            mdc_content = self._convert_to_mdc(content)
            target = dest / f"{skill_path.stem}.mdc"
        staged = target.with_name(f".{target.name}.source")
        if dry_run:
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            staged.write_text(mdc_content, encoding="utf-8")
            return install_file(staged, target, force=force, dry_run=False)
        finally:
            staged.unlink(missing_ok=True)

    def _convert_to_mdc(self, content: str) -> str:
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                fm = content[3:end].strip()
                body = content[end + 3:].strip()
                return f"---\n{fm}\nglobs:\nalwaysApply: false\n---\n{body}"
        return content
