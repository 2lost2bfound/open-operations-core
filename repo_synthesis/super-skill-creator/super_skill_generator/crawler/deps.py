"""Dependency scanner — auto-discovers project deps and generates crawl rules."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CrawlRule:
    url: str
    subpaths: bool = True
    action: str = "include"

    def to_dict(self) -> dict[str, str | bool]:
        return {"url": self.url, "subpaths": self.subpaths, "action": self.action}


class DependencyScanner:
    def scan(self, project_dir: Path) -> list[CrawlRule]:
        rules: list[CrawlRule] = []
        rules.extend(self._scan_npm(project_dir))
        rules.extend(self._scan_go(project_dir))
        rules.extend(self._scan_python(project_dir))
        return rules

    def _scan_npm(self, project_dir: Path) -> list[CrawlRule]:
        pkg = project_dir / "package.json"
        if not pkg.exists():
            return []
        try:
            data = json.loads(pkg.read_text())
        except json.JSONDecodeError:
            return []
        rules = []
        for section in ("dependencies", "devDependencies"):
            for name, version in data.get(section, {}).items():
                clean_ver = re.sub(r"[\^~>=<]", "", str(version))
                rules.append(
                    CrawlRule(
                        url=f"https://www.npmjs.com/package/{name}/v/{clean_ver}",
                        subpaths=True,
                    )
                )
        return rules

    def _scan_go(self, project_dir: Path) -> list[CrawlRule]:
        gomod = project_dir / "go.mod"
        if not gomod.exists():
            return []
        rules = []
        in_require = False
        for line in gomod.read_text().splitlines():
            line = line.strip()
            if line.startswith("require ("):
                in_require = True
                continue
            if line == ")":
                in_require = False
                continue
            if in_require or line.startswith("require "):
                parts = line.replace("require ", "").split()
                if len(parts) >= 2:
                    module, version = parts[0], parts[1]
                    rules.append(
                        CrawlRule(
                            url=f"https://pkg.go.dev/{module}@{version}",
                            subpaths=True,
                        )
                    )
        return rules

    def _scan_python(self, project_dir: Path) -> list[CrawlRule]:
        rules = []
        for req_file in ("requirements.txt", "pyproject.toml"):
            path = project_dir / req_file
            if path.exists():
                text = path.read_text()
                for line in text.splitlines():
                    match = re.match(r"^([a-zA-Z0-9_-]+)", line.strip())
                    if match and not line.strip().startswith("#"):
                        name = match.group(1)
                        rules.append(
                            CrawlRule(
                                url=f"https://pypi.org/project/{name}/",
                                subpaths=False,
                            )
                        )
        return rules
