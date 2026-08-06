"""Configuration loader — TOML-based with sensible defaults."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CrawlConfig:
    output_dir: str = ".skillscache"
    flat: bool = False
    max_depth: int = 3
    parallelism: int = 4
    respect_robots: bool = True
    user_agent: str = "SuperSkillGenerator/0.1"
    rules: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class QualityConfig:
    max_description_length: int = 1024
    max_name_length: int = 64
    require_frontmatter: bool = True
    security_scan: bool = True
    staleness_days: int = 90


@dataclass
class PipelineConfig:
    phases: list[str] = field(
        default_factory=lambda: [
            "discovery",
            "design",
            "architecture",
            "detection",
            "implementation",
        ]
    )
    auto_advance: bool = True
    strict_gates: bool = True


@dataclass
class SSGConfig:
    project_name: str = "my-skill"
    output_dir: str = "./output"
    platforms: list[str] = field(
        default_factory=lambda: [
            "claude-code",
            "cursor",
            "windsurf",
            "codex",
            "cline",
            "aider",
            "copilot",
            "trae",
            "kiro",
            "amp",
        ]
    )
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    crawl: CrawlConfig = field(default_factory=CrawlConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)

    @classmethod
    def load(cls, path: Path | None = None) -> SSGConfig:
        if path is None:
            for candidate in [Path("ssg.toml"), Path(".ssg.toml")]:
                if candidate.exists():
                    path = candidate
                    break
        if path is None or not path.exists():
            return cls()
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> SSGConfig:
        cfg = cls()
        cfg.project_name = data.get("project_name", cfg.project_name)
        cfg.output_dir = data.get("output_dir", cfg.output_dir)
        cfg.platforms = data.get("platforms", cfg.platforms)
        if "pipeline" in data:
            p = data["pipeline"]
            cfg.pipeline = PipelineConfig(
                phases=p.get("phases", cfg.pipeline.phases),
                auto_advance=p.get("auto_advance", cfg.pipeline.auto_advance),
                strict_gates=p.get("strict_gates", cfg.pipeline.strict_gates),
            )
        if "crawl" in data:
            c = data["crawl"]
            cfg.crawl = CrawlConfig(
                output_dir=c.get("output_dir", cfg.crawl.output_dir),
                flat=c.get("flat", cfg.crawl.flat),
                max_depth=c.get("max_depth", cfg.crawl.max_depth),
                parallelism=c.get("parallelism", cfg.crawl.parallelism),
                respect_robots=c.get("respect_robots", cfg.crawl.respect_robots),
                user_agent=c.get("user_agent", cfg.crawl.user_agent),
                rules=c.get("rules", cfg.crawl.rules),
            )
        if "quality" in data:
            q = data["quality"]
            cfg.quality = QualityConfig(
                max_description_length=q.get(
                    "max_description_length", cfg.quality.max_description_length
                ),
                max_name_length=q.get("max_name_length", cfg.quality.max_name_length),
                require_frontmatter=q.get(
                    "require_frontmatter", cfg.quality.require_frontmatter
                ),
                security_scan=q.get("security_scan", cfg.quality.security_scan),
                staleness_days=q.get("staleness_days", cfg.quality.staleness_days),
            )
        return cfg
