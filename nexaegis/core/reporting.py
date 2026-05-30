from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from nexaegis.core.config import NexAegisConfig
from nexaegis.scanners.project import ProjectScanResult, scan_project
from nexaegis.scanners.risk import RiskResult, analyze_risk
from nexaegis.scanners.security import SecurityResult, scan_security


@dataclass(frozen=True)
class ProjectReport:
    doctor: ProjectScanResult
    risk: RiskResult
    security: SecurityResult

    def to_dict(self) -> dict[str, object]:
        return {
            "doctor": self.doctor.to_dict(),
            "risk": self.risk.to_dict(),
            "security": self.security.to_dict(),
        }


def build_project_report(project_root: Path, config: NexAegisConfig) -> ProjectReport:
    return ProjectReport(
        doctor=scan_project(project_root),
        risk=analyze_risk(project_root, weights=config.risk_weights),
        security=scan_security(project_root),
    )


def report_to_json(report: ProjectReport) -> str:
    return json.dumps(report.to_dict(), indent=2)


def report_to_sarif(report: ProjectReport) -> str:
    findings = report.security.findings
    rule_titles = sorted({finding.title for finding in findings})
    rule_ids = {title: _sarif_rule_id(title) for title in rule_titles}
    rules = [
        {
            "id": rule_ids[title],
            "name": title,
            "shortDescription": {"text": title},
            "helpUri": "https://github.com/nexaegis/nexaegis-ai",
        }
        for title in rule_titles
    ]
    results = []
    for finding in findings:
        result: dict[str, object] = {
            "ruleId": rule_ids[finding.title],
            "level": _sarif_level(finding.severity),
            "message": {"text": finding.detail or finding.title},
        }
        if finding.path:
            result["locations"] = [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": finding.path},
                    }
                }
            ]
        results.append(result)

    payload = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "NexAegis AI",
                        "informationUri": "https://github.com/nexaegis/nexaegis-ai",
                        "rules": rules,
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(payload, indent=2)


def report_to_markdown(report: ProjectReport) -> str:
    doctor_counts = report.doctor.status_counts()
    findings = report.security.findings
    security_lines = (
        "\n".join(
            f"- **{finding.severity}**: {finding.title}"
            + (f" (`{finding.path}`)" if finding.path else "")
            for finding in findings
        )
        if findings
        else "- No built-in security findings."
    )
    risk_reasons = "\n".join(f"- {reason}" for reason in report.risk.reasons)
    recommendations = "\n".join(f"- {item}" for item in report.risk.recommendations)

    return "\n".join(
        [
            "# NexAegis AI Report",
            "",
            f"- Health score: **{report.doctor.score}/100**",
            f"- Risk score: **{report.risk.score}/100 ({report.risk.level})**",
            f"- Security score: **{report.security.score}/100**",
            "",
            "## Doctor",
            "",
            f"- Good: {doctor_counts.get('Good', 0)}",
            f"- Warning: {doctor_counts.get('Warning', 0)}",
            f"- Missing: {doctor_counts.get('Missing', 0)}",
            "",
            "## Risk Reasons",
            "",
            risk_reasons,
            "",
            "## Recommendations",
            "",
            recommendations,
            "",
            "## Security Findings",
            "",
            security_lines,
            "",
        ]
    )


def render_report(report: ProjectReport, report_format: str) -> str:
    normalized = report_format.lower()
    if normalized == "json":
        return report_to_json(report)
    if normalized == "sarif":
        return report_to_sarif(report)
    if normalized in {"md", "markdown"}:
        return report_to_markdown(report)
    raise ValueError(f"Unsupported report format: {report_format}")


def _sarif_rule_id(title: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return f"nexaegis.{normalized or 'finding'}"


def _sarif_level(severity: str) -> str:
    normalized = severity.lower()
    if normalized == "high":
        return "error"
    if normalized == "medium":
        return "warning"
    return "note"
