"""Phase 1: Discovery — derive intent from input evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DiscoveryResult:
    intent: str
    domain: str
    triggers: list[str]
    input_types: list[str]
    output_artifacts: list[str]
    constraints: list[str]


class DiscoveryPhase:
    def __init__(self, config: Any) -> None:
        self.config = config

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        description = context["description"]
        result = self._derive_intent(description)
        context["artifacts"]["discovery"] = {
            "intent": result.intent,
            "domain": result.domain,
            "triggers": result.triggers,
            "input_types": result.input_types,
            "output_artifacts": result.output_artifacts,
            "constraints": result.constraints,
        }
        return context

    def _derive_intent(self, description: str) -> DiscoveryResult:
        desc_lower = description.lower()
        domain = self._infer_domain(desc_lower)
        triggers = self._extract_triggers(desc_lower)
        input_types = self._infer_inputs(desc_lower)
        output_artifacts = self._infer_outputs(desc_lower)
        constraints = self._infer_constraints(desc_lower)
        return DiscoveryResult(
            intent=description.strip(),
            domain=domain,
            triggers=triggers,
            input_types=input_types,
            output_artifacts=output_artifacts,
            constraints=constraints,
        )

    def _infer_domain(self, desc: str) -> str:
        domains = {
            "code": ["code", "function", "api", "refactor", "debug", "test", "build"],
            "data": ["data", "csv", "json", "database", "query", "etl", "pipeline"],
            "docs": ["doc", "readme", "guide", "tutorial", "wiki", "knowledge"],
            "devops": ["deploy", "ci", "cd", "docker", "k8s", "infra", "monitor"],
            "design": ["ui", "ux", "design", "layout", "component", "style"],
            "security": ["security", "audit", "vuln", "pentest", "scan", "harden"],
            "writing": ["write", "article", "blog", "edit", "proofread", "content"],
        }
        for domain, keywords in domains.items():
            if any(kw in desc for kw in keywords):
                return domain
        return "general"

    def _extract_triggers(self, desc: str) -> list[str]:
        triggers = []
        trigger_patterns = [
            "when", "if", "use when", "trigger", "invoke",
            "run", "execute", "start", "create", "generate",
        ]
        for pattern in trigger_patterns:
            if pattern in desc:
                triggers.append(pattern)
        return triggers or ["manual invocation"]

    def _infer_inputs(self, desc: str) -> list[str]:
        inputs = []
        input_map = {
            "file": ["file", "path", "directory", "folder"],
            "text": ["text", "string", "description", "prompt", "message"],
            "url": ["url", "link", "website", "page", "site"],
            "code": ["code", "source", "script", "function"],
            "config": ["config", "yaml", "toml", "json", "settings"],
        }
        for input_type, keywords in input_map.items():
            if any(kw in desc for kw in keywords):
                inputs.append(input_type)
        return inputs or ["text"]

    def _infer_outputs(self, desc: str) -> list[str]:
        outputs = []
        output_map = {
            "file": ["file", "write", "save", "export", "generate"],
            "report": ["report", "summary", "analysis", "review"],
            "code": ["code", "script", "function", "module"],
            "markdown": ["markdown", "md", "document", "skill"],
        }
        for output_type, keywords in output_map.items():
            if any(kw in desc for kw in keywords):
                outputs.append(output_type)
        return outputs or ["markdown"]

    def _infer_constraints(self, desc: str) -> list[str]:
        constraints = []
        if "safe" in desc or "security" in desc:
            constraints.append("security-first")
        if "fast" in desc or "quick" in desc:
            constraints.append("performance-priority")
        if "offline" in desc or "local" in desc:
            constraints.append("no-network")
        if "idempotent" in desc:
            constraints.append("idempotent")
        return constraints
