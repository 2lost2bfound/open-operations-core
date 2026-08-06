"""Phase 5: Implementation — generate platform-agnostic, constitution-compliant skills."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any


class ImplementationPhase:
    def __init__(self, config: Any) -> None:
        self.config = config

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        output_dir = context["output_dir"]
        skill_name = context["skill_name"]
        skill_dir = output_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        artifacts = context["artifacts"]
        source_url = context.get("source_url", "")
        crawled_content = context.get("crawled_content", "")
        self._write_skill_md(skill_dir, skill_name, artifacts, source_url, crawled_content)
        self._write_workflow(skill_dir, skill_name, artifacts)
        self._write_main_script(skill_dir, skill_name, artifacts)
        context["artifacts"]["implementation"] = {
            "files_created": list(skill_dir.rglob("*")),
            "skill_dir": str(skill_dir),
        }
        return context

    def _write_skill_md(
        self, skill_dir: Path, name: str, artifacts: dict, source_url: str, crawled_content: str = ""
    ) -> None:
        design = artifacts.get("design", {})
        discovery = artifacts.get("discovery", {})
        domain = discovery.get("domain", "general")
        today = date.today().isoformat()
        lines = [
            "---",
            f'name: "{name}"',
            f'description: "{design.get("description", "")}"',
            "version: 1.0.0",
            f"repo: {name}",
            f"url: {source_url or 'N/A'}",
            f"floor: {domain}",
            "status: reviewed",
            f"added: {today}",
            "overlaps-with: []",
            "feeds-into: []",
            "platform: agnostic",
        ]
        triggers = design.get("triggers", [])
        if triggers:
            lines.append("triggers:")
            for t in triggers:
                lines.append(f'  - "{t}"')
        lines.append("---")
        lines.append("")
        lines.append(f"# {name}")
        lines.append("")
        lines.append("> This skill is platform-agnostic. It works with any AI agent")
        lines.append("> that supports Markdown skill files (Claude Code, Codex,")
        lines.append("> OpenCode, Cursor, Windsurf, Cline, Aider, or custom agents).")
        lines.append("")
        lines.append("## Constitution Compliance")
        lines.append("")
        lines.append("This skill follows the super-repo constitution rules:")
        lines.append("")
        lines.append("- **Frontmatter**: Every note and output gets frontmatter (repo, url, floor, status, added, overlaps-with, feeds-into).")
        lines.append("- **Append-only**: Never delete another agent's log entries.")
        lines.append("- **One task, one owner**: If no clear owner, flag for the human.")
        lines.append("- **Escalate ambiguity**: Use `## Open Questions` rather than silently assuming.")
        lines.append("- **Pre-flight**: Check INDEX.md `last-scanned` before big projects.")
        lines.append("")
        lines.append("## When to Use")
        for t in triggers:
            lines.append(f"- {t}")
        lines.append("")
        lines.append("## Workflow")
        for i, step in enumerate(design.get("workflow_steps", []), 1):
            lines.append(f"{i}. {step}")
        lines.append("")
        lines.append("## Inputs")
        for inp in design.get("inputs", []):
            req = "required" if inp.get("required") else "optional"
            lines.append(f"- **{inp['type']}** ({req}): {inp.get('description', '')}")
        lines.append("")
        lines.append("## Outputs")
        for out in design.get("outputs", []):
            lines.append(f"- **{out['type']}**: {out.get('description', '')}")
        lines.append("")
        lines.append("## Open Questions")
        lines.append("")
        lines.append("_None yet. Add ambiguities here rather than assuming._")
        if crawled_content:
            lines.append("")
            lines.append("## Source Content")
            lines.append("")
            lines.append("_The following content was crawled from the source URL and used to generate this skill:_")
            lines.append("")
            lines.append(crawled_content)
        (skill_dir / "SKILL.md").write_text("\n".join(lines))

    def _write_workflow(self, skill_dir: Path, name: str, artifacts: dict) -> None:
        design = artifacts.get("design", {})
        refs_dir = skill_dir / "references"
        refs_dir.mkdir(exist_ok=True)
        lines = [f"# {name} Workflow", ""]
        for i, step in enumerate(design.get("workflow_steps", []), 1):
            lines.append(f"## Step {i}: {step}")
            lines.append("")
        lines.append("## Error Handling")
        for err, handling in design.get("error_handling", {}).items():
            lines.append(f"- **{err}**: {handling}")
        (refs_dir / "workflow.md").write_text("\n".join(lines))

    def _write_main_script(self, skill_dir: Path, name: str, artifacts: dict) -> None:
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        arch = artifacts.get("architecture", {})
        deps = arch.get("dependencies", [])
        lines = ["#!/usr/bin/env python3", '"""Main script for {name} skill."""', ""]
        for dep in deps:
            lines.append(f"import {dep}")
        lines.extend([
            "",
            "def main():",
            '    print("Skill executed successfully")',
            "",
            'if __name__ == "__main__":',
            "    main()",
        ])
        (scripts_dir / "main.py").write_text("\n".join(lines))
