# Super-Skill Generator (ssg)

Unified skill creation toolkit that synthesizes the best of three open-source projects into a single CLI tool for generating, crawling, validating, and installing agent skills across 12+ platforms.

## What It Does

- **Create skills** from natural-language descriptions via a deterministic, template-based 5-phase pipeline (Discovery → Design → Architecture → Detection → Implementation)
- **Crawl documentation** from URLs into token-efficient Markdown with frontmatter metadata
- **Scan dependencies** (NPM, Go, Python) and auto-generate crawl rules
- **Validate quality** against frontmatter, size, and structural standards
- **Security scan** for dangerous patterns (shell injection, secrets, privilege escalation)
- **Install cross-platform** to 12+ agent platforms (Claude Code, Cursor, Windsurf, Codex, OpenCode, Cline, Aider, Copilot, Trae, Kiro, Amp, Goose)

## Installation

```bash
pip install -e .
```

## Quick Start

`ssg create` currently uses local heuristics and templates. It does not call an LLM endpoint; the orchestrator harness is a separate optional component.

```bash
# Create a skill from a description
ssg create "Generate API documentation from Python docstrings" --name api-docs

# Crawl documentation into Markdown references
ssg crawl https://docs.python.org/3/library/ --depth 2 --output ./references

# Validate a generated skill
ssg validate ./output/api-docs

# Security scan
ssg security ./output/api-docs

# Install to multiple platforms
ssg install ./output/api-docs --platform claude-code --platform cursor

# Scan project dependencies for crawl rules
ssg scan-deps ./my-project
```

## Configuration

Create `ssg.toml` in your project root:

```toml
project_name = "my-skill"
output_dir = "./output"
platforms = ["claude-code", "cursor", "opencode"]

[pipeline]
phases = ["discovery", "design", "architecture", "detection", "implementation"]
auto_advance = true
strict_gates = true

[crawl]
output_dir = ".skillscache"
flat = false
max_depth = 3
parallelism = 4
user_agent = "SuperSkillGenerator/0.1"

[quality]
max_description_length = 1024
max_name_length = 64
require_frontmatter = true
security_scan = true
staleness_days = 90
```

## Architecture

```
super-skill-creator/
├── cli.py              # Click CLI entry point
├── config.py           # TOML config loader
├── pipeline/           # 5-phase creation pipeline
│   ├── engine.py       # Pipeline orchestrator
│   ├── discovery.py    # Phase 1: Intent derivation
│   ├── design.py       # Phase 2: Structure design
│   ├── architecture.py # Phase 3: File planning
│   ├── detection.py    # Phase 4: Environment detection
│   └── implementation.py # Phase 5: File generation
├── crawler/            # Web crawling engine
│   ├── engine.py       # Recursive crawler
│   ├── html_to_md.py   # HTML→Markdown converter
│   ├── metadata.py     # Metadata extractor
│   └── deps.py         # Dependency scanner
├── quality/            # Quality gates
│   ├── validator.py    # Skill validation
│   └── security.py     # Security scanner
├── platforms/          # Cross-platform support
│   ├── registry.py     # Platform registry
│   └── adapters/       # Platform-specific adapters
│       ├── base.py
│       ├── native.py   # 10 native SKILL.md platforms
│       ├── cursor.py   # .mdc format adapter
│       └── windsurf.py # Windsurf format adapter
└── templates/          # Jinja2 templates
```

## Supported Platforms

| Platform | Format | Tier |
|----------|--------|------|
| Claude Code | SKILL.md | Native |
| Codex | SKILL.md | Native |
| OpenCode | SKILL.md | Native |
| Cline | SKILL.md | Native |
| Aider | SKILL.md | Native |
| Copilot | SKILL.md | Native |
| Trae | SKILL.md | Native |
| Kiro | SKILL.md | Native |
| Amp | SKILL.md | Native |
| Goose | SKILL.md | Native |
| Cursor | .mdc | Adapted |
| Windsurf | .md | Adapted |

## Lineage

Synthesized from:
- **agent-skill-creator** (Target A): 5-phase pipeline, quality gates, eval system, cross-platform installers
- **agent-skills-generator** (Target B): Web crawling engine, HTML→Markdown, dependency scanning, incremental crawl

## License

MIT
