"""Skill validator — quality gates for generated skills."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..config import QualityConfig


@dataclass
class ValidationIssue:
    severity: str
    message: str
    file: str = ""


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def summary(self) -> str:
        if not self.issues:
            return "Validation passed: no issues found."
        lines = [f"Found {len(self.issues)} issue(s):"]
        for issue in self.issues:
            loc = f" [{issue.file}]" if issue.file else ""
            lines.append(f"  [{issue.severity}]{loc} {issue.message}")
        return "\n".join(lines)


class SkillValidator:
    def __init__(self, config: QualityConfig) -> None:
        self.config = config

    def validate(self, skill_path: Path) -> ValidationReport:
        report = ValidationReport()
        if skill_path.is_file():
            self._validate_file(skill_path, report)
        elif skill_path.is_dir():
            skill_md = skill_path / "SKILL.md"
            if not skill_md.exists():
                report.issues.append(
                    ValidationIssue("error", "Missing SKILL.md", str(skill_path))
                )
            else:
                self._validate_file(skill_md, report)
        else:
            report.issues.append(
                ValidationIssue("error", "Path does not exist", str(skill_path))
            )
        return report

    def _validate_file(self, path: Path, report: ValidationReport) -> None:
        content = path.read_text(encoding="utf-8", errors="ignore")
        if self.config.require_frontmatter:
            if not content.startswith("---"):
                report.issues.append(
                    ValidationIssue("error", "Missing YAML frontmatter", str(path))
                )
            else:
                self._validate_frontmatter(content, report, str(path))
        if len(content) > 50000:
            report.issues.append(
                ValidationIssue("warning", "File exceeds 50KB", str(path))
            )

    def _validate_frontmatter(
        self, content: str, report: ValidationReport, filepath: str
    ) -> None:
        end = content.find("---", 3)
        if end == -1:
            report.issues.append(
                ValidationIssue("error", "Unclosed frontmatter", filepath)
            )
            return
        fm = content[3:end]
        if "name:" not in fm:
            report.issues.append(
                ValidationIssue("error", "Missing 'name' in frontmatter", filepath)
            )
        if "description:" not in fm:
            report.issues.append(
                ValidationIssue("error", "Missing 'description' in frontmatter", filepath)
            )
        name_match = re.search(r'name:\s*"?(.+?)"?\s*$', fm, re.MULTILINE)
        if name_match:
            name = name_match.group(1).strip('"')
            if len(name) > self.config.max_name_length:
                report.issues.append(
                    ValidationIssue(
                        "warning",
                        f"Name exceeds {self.config.max_name_length} chars",
                        filepath,
                    )
                )
