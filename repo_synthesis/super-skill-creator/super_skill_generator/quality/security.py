"""Security scanner — detects dangerous patterns in skill files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SecurityFinding:
    severity: str
    pattern: str
    location: str
    line: int = 0


@dataclass
class SecurityReport:
    findings: list[SecurityFinding] = field(default_factory=list)

    @property
    def severity(self) -> str:
        if any(f.severity == "critical" for f in self.findings):
            return "critical"
        if any(f.severity == "high" for f in self.findings):
            return "high"
        if any(f.severity == "medium" for f in self.findings):
            return "medium"
        return "low"

    def summary(self) -> str:
        if not self.findings:
            return "Security scan passed: no issues found."
        lines = [f"Security scan: {len(self.findings)} finding(s), severity={self.severity}"]
        for f in self.findings:
            lines.append(f"  [{f.severity}] {f.pattern} at {f.location}:{f.line}")
        return "\n".join(lines)


class SecurityScanner:
    DANGEROUS_PATTERNS = [
        (r"rm\s+-rf\s+/", "critical", "Recursive root deletion"),
        (r"curl\s+.*\|\s*(bash|sh)", "critical", "Pipe to shell execution"),
        (r"wget\s+.*\|\s*(bash|sh)", "critical", "Pipe to shell execution"),
        (r"eval\s*\(", "high", "Dynamic code evaluation"),
        (r"exec\s*\(", "high", "Dynamic code execution"),
        (r"__import__\s*\(", "high", "Dynamic import"),
        (r"subprocess\.\w+\(", "medium", "Subprocess execution"),
        (r"os\.system\s*\(", "medium", "OS command execution"),
        (r"open\s*\(.*['\"]w", "medium", "File write operation"),
        (r"API_KEY|SECRET|TOKEN|PASSWORD", "high", "Potential secret reference"),
        (r"sudo\s+", "medium", "Privilege escalation"),
        (r"chmod\s+777", "medium", "Overly permissive permissions"),
    ]

    def scan(self, path: Path) -> SecurityReport:
        report = SecurityReport()
        if path.is_file():
            self._scan_file(path, report)
        elif path.is_dir():
            for file in path.rglob("*"):
                if file.is_file() and file.suffix in (".py", ".sh", ".md", ".js", ".ts"):
                    self._scan_file(file, report)
        return report

    def _scan_file(self, path: Path, report: SecurityReport) -> None:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return
        for i, line in enumerate(lines, 1):
            for pattern, severity, desc in self.DANGEROUS_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    report.findings.append(
                        SecurityFinding(
                            severity=severity,
                            pattern=desc,
                            location=str(path),
                            line=i,
                        )
                    )
