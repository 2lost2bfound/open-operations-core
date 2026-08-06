"""Phase 3: Architecture — plan file structure and dependencies."""

from __future__ import annotations

from typing import Any


class ArchitecturePhase:
    def __init__(self, config: Any) -> None:
        self.config = config

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        design = context["artifacts"]["design"]
        arch = {
            "file_structure": self._plan_files(design),
            "dependencies": self._plan_deps(design),
            "templates_needed": self._plan_templates(design),
            "platform_targets": context.get("platforms", self.config.platforms),
        }
        context["artifacts"]["architecture"] = arch
        return context

    def _plan_files(self, design: dict) -> list[str]:
        name = design["skill_name"]
        return [
            f"{name}/SKILL.md",
            f"{name}/references/workflow.md",
            f"{name}/scripts/main.py",
            f"{name}/tests/test_{name}.py",
        ]

    def _plan_deps(self, design: dict) -> list[str]:
        deps = []
        for inp in design.get("inputs", []):
            if inp["type"] == "url":
                deps.extend(["httpx", "parsel"])
            elif inp["type"] == "file":
                deps.append("pathlib")
        return list(set(deps))

    def _plan_templates(self, design: dict) -> list[str]:
        return ["skill_md.j2", "workflow_md.j2"]
