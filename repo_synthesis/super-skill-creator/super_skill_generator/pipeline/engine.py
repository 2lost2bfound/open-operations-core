"""Pipeline engine — orchestrates the 5-phase skill creation flow."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import SSGConfig


@dataclass
class PipelineResult:
    success: bool
    output_path: Path | None = None
    error: str | None = None
    phases_completed: list[str] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)


class PipelineEngine:
    def __init__(self, config: SSGConfig) -> None:
        self.config = config
        self._phases: list[Any] = []
        self._load_phases()

    def _load_phases(self) -> None:
        from .discovery import DiscoveryPhase
        from .design import DesignPhase
        from .architecture import ArchitecturePhase
        from .detection import DetectionPhase
        from .implementation import ImplementationPhase

        phase_map = {
            "discovery": DiscoveryPhase,
            "design": DesignPhase,
            "architecture": ArchitecturePhase,
            "detection": DetectionPhase,
            "implementation": ImplementationPhase,
        }
        for name in self.config.pipeline.phases:
            cls = phase_map.get(name)
            if cls:
                self._phases.append(cls(self.config))

    def run(
        self,
        description: str,
        skill_name: str,
        output_dir: Path,
        source_url: str = "",
        crawled_content: str = "",
    ) -> PipelineResult:
        context: dict[str, Any] = {
            "description": description,
            "skill_name": skill_name,
            "output_dir": output_dir,
            "source_url": source_url,
            "crawled_content": crawled_content,
            "artifacts": {},
        }
        result = PipelineResult(success=False)
        for phase in self._phases:
            phase_name = phase.__class__.__name__
            try:
                context = phase.execute(context)
                result.phases_completed.append(phase_name)
            except Exception as e:
                result.error = f"{phase_name} failed: {e}"
                return result
        result.success = True
        result.output_path = output_dir / skill_name
        result.artifacts = context.get("artifacts", {})
        return result
