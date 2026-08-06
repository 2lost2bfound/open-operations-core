"""Phase 2: Design — define skill structure and behavior."""

from __future__ import annotations

from typing import Any


class DesignPhase:
    def __init__(self, config: Any) -> None:
        self.config = config

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        discovery = context["artifacts"]["discovery"]
        design = {
            "skill_name": context["skill_name"],
            "description": discovery["intent"],
            "triggers": self._build_triggers(discovery),
            "inputs": self._build_inputs(discovery),
            "outputs": self._build_outputs(discovery),
            "workflow_steps": self._build_workflow(discovery),
            "error_handling": self._build_error_handling(discovery),
        }
        context["artifacts"]["design"] = design
        return context

    def _build_triggers(self, discovery: dict) -> list[str]:
        raw = discovery.get("triggers", [])
        return [f"User says '{t}' or similar phrasing" for t in raw]

    def _build_inputs(self, discovery: dict) -> list[dict[str, str]]:
        inputs = []
        for inp in discovery.get("input_types", []):
            inputs.append({"type": inp, "required": True, "description": f"The {inp} to process"})
        return inputs

    def _build_outputs(self, discovery: dict) -> list[dict[str, str]]:
        outputs = []
        for out in discovery.get("output_artifacts", []):
            outputs.append({"type": out, "description": f"Generated {out}"})
        return outputs

    def _build_workflow(self, discovery: dict) -> list[str]:
        steps = ["Parse and validate input"]
        domain = discovery.get("domain", "general")
        if domain == "code":
            steps.extend(["Analyze code structure", "Apply transformations", "Generate output code"])
        elif domain == "data":
            steps.extend(["Load data source", "Process and transform", "Generate report"])
        elif domain == "docs":
            steps.extend(["Extract content", "Structure and organize", "Generate documentation"])
        else:
            steps.extend(["Process input", "Apply domain logic", "Generate output"])
        steps.append("Validate output quality")
        return steps

    def _build_error_handling(self, discovery: dict) -> dict[str, str]:
        return {
            "invalid_input": "Report clear error with expected format",
            "processing_failure": "Log error, provide fallback output",
            "timeout": "Abort gracefully with partial results",
        }
