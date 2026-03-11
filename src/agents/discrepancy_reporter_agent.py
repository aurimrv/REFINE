"""
DiscrepancyReporterAgent
------------------------
Responsible for comparing the endpoints and response codes extracted from the
OpenAPI specification against those found in the source code implementation,
and producing a detailed Markdown discrepancy report.

Discrepancy categories:
  - MISSING_IN_IMPL  : endpoint present in spec but not found in the implementation
  - MISSING_IN_SPEC  : endpoint found in the implementation but absent from the spec
  - RETCODE_MISMATCH : endpoint exists in both, but response codes differ
  - PARAM_MISMATCH   : endpoint exists in both, but parameters differ
  - MATCH            : endpoint and response codes are fully aligned
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from src.agents.source_analyzer_agent import ImplementedEndpoint
from src.models.openapi_models import EndpointInfo
from src.utils.logger import setup_logger

logger = setup_logger("discrepancy_reporter_agent")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class EndpointDiscrepancy:
    """Represents a single discrepancy finding between spec and implementation."""
    category: str          # One of: MATCH, MISSING_IN_IMPL, MISSING_IN_SPEC, RETCODE_MISMATCH, PARAM_MISMATCH
    method: str
    path: str
    spec_codes: List[str] = field(default_factory=list)
    impl_codes: List[str] = field(default_factory=list)
    spec_params: List[dict] = field(default_factory=list)
    impl_params: List[dict] = field(default_factory=list)
    notes: str = ""


@dataclass
class DiscrepancyReport:
    """Aggregated discrepancy report between spec and implementation."""
    spec_file: str
    src_home: str
    generated_at: str
    findings: List[EndpointDiscrepancy] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.findings)

    @property
    def matches(self) -> int:
        return sum(1 for f in self.findings if f.category == "MATCH")

    @property
    def missing_in_impl(self) -> int:
        return sum(1 for f in self.findings if f.category == "MISSING_IN_IMPL")

    @property
    def missing_in_spec(self) -> int:
        return sum(1 for f in self.findings if f.category == "MISSING_IN_SPEC")

    @property
    def retcode_mismatches(self) -> int:
        return sum(1 for f in self.findings if f.category == "RETCODE_MISMATCH")

    @property
    def param_mismatches(self) -> int:
        return sum(1 for f in self.findings if f.category == "PARAM_MISMATCH")

    @property
    def has_discrepancies(self) -> bool:
        return self.total > self.matches


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class DiscrepancyReporterAgent:
    """
    Compares spec endpoints vs implemented endpoints and generates a
    detailed Markdown discrepancy report.
    """

    def __init__(
        self,
        spec_endpoints: List[EndpointInfo],
        impl_endpoints: List[ImplementedEndpoint],
        spec_file: Path,
        src_home: Path,
    ) -> None:
        self.spec_endpoints = spec_endpoints
        self.impl_endpoints = impl_endpoints
        self.spec_file = spec_file
        self.src_home = src_home
        logger.info(
            "DiscrepancyReporterAgent initialized. "
            "Spec endpoints: %d, Implemented endpoints: %d.",
            len(spec_endpoints),
            len(impl_endpoints),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compare(self) -> DiscrepancyReport:
        """
        Perform the comparison and return a DiscrepancyReport.
        """
        report = DiscrepancyReport(
            spec_file=str(self.spec_file),
            src_home=str(self.src_home),
            generated_at=datetime.now().isoformat(timespec="seconds"),
        )

        # Build lookup maps
        spec_map = {(ep.method.upper(), self._normalize_path(ep.path)): ep
                    for ep in self.spec_endpoints}
        impl_map = {(ep.method.upper(), self._normalize_path(ep.path)): ep
                    for ep in self.impl_endpoints}

        all_keys = set(spec_map.keys()) | set(impl_map.keys())

        for key in sorted(all_keys):
            method, path = key
            in_spec = key in spec_map
            in_impl = key in impl_map

            if in_spec and not in_impl:
                report.findings.append(EndpointDiscrepancy(
                    category="MISSING_IN_IMPL",
                    method=method,
                    path=path,
                    spec_codes=list(spec_map[key].response_codes),
                    notes="Endpoint is declared in the spec but not found in the source code.",
                ))

            elif in_impl and not in_spec:
                report.findings.append(EndpointDiscrepancy(
                    category="MISSING_IN_SPEC",
                    method=method,
                    path=path,
                    impl_codes=list(impl_map[key].response_codes),
                    notes="Endpoint is implemented in the source code but absent from the spec.",
                ))

            else:
                # Present in both — check response codes and parameters
                spec_ep = spec_map[key]
                impl_ep = impl_map[key]

                spec_codes = set(self._normalize_code(c) for c in spec_ep.response_codes)
                impl_codes = set(self._normalize_code(c) for c in impl_ep.response_codes)

                only_in_spec = sorted(spec_codes - impl_codes)
                only_in_impl = sorted(impl_codes - spec_codes)

                code_mismatch = bool(only_in_spec or only_in_impl)

                # Parameter comparison (name + location)
                spec_params = {(p.get("name", ""), p.get("in", "")): p
                               for p in (spec_ep.parameters or [])}
                impl_params = {(p.get("name", ""), p.get("in", "")): p
                               for p in (impl_ep.parameters or [])}
                param_keys_spec = set(spec_params.keys())
                param_keys_impl = set(impl_params.keys())
                only_params_in_spec = sorted(param_keys_spec - param_keys_impl)
                only_params_in_impl = sorted(param_keys_impl - param_keys_spec)
                param_mismatch = bool(only_params_in_spec or only_params_in_impl)

                if code_mismatch and param_mismatch:
                    notes = (
                        f"Response code mismatch — only in spec: {only_in_spec}; "
                        f"only in impl: {only_in_impl}. "
                        f"Parameter mismatch — only in spec: {only_params_in_spec}; "
                        f"only in impl: {only_params_in_impl}."
                    )
                    report.findings.append(EndpointDiscrepancy(
                        category="RETCODE_MISMATCH",
                        method=method,
                        path=path,
                        spec_codes=sorted(spec_codes),
                        impl_codes=sorted(impl_codes),
                        spec_params=list(spec_params.values()),
                        impl_params=list(impl_params.values()),
                        notes=notes,
                    ))
                elif code_mismatch:
                    notes = (
                        f"Response codes only in spec: {only_in_spec}. "
                        f"Response codes only in impl: {only_in_impl}."
                    )
                    report.findings.append(EndpointDiscrepancy(
                        category="RETCODE_MISMATCH",
                        method=method,
                        path=path,
                        spec_codes=sorted(spec_codes),
                        impl_codes=sorted(impl_codes),
                        spec_params=list(spec_params.values()),
                        impl_params=list(impl_params.values()),
                        notes=notes,
                    ))
                elif param_mismatch:
                    notes = (
                        f"Parameters only in spec: {only_params_in_spec}. "
                        f"Parameters only in impl: {only_params_in_impl}."
                    )
                    report.findings.append(EndpointDiscrepancy(
                        category="PARAM_MISMATCH",
                        method=method,
                        path=path,
                        spec_codes=sorted(spec_codes),
                        impl_codes=sorted(impl_codes),
                        spec_params=list(spec_params.values()),
                        impl_params=list(impl_params.values()),
                        notes=notes,
                    ))
                else:
                    report.findings.append(EndpointDiscrepancy(
                        category="MATCH",
                        method=method,
                        path=path,
                        spec_codes=sorted(spec_codes),
                        impl_codes=sorted(impl_codes),
                        notes="Endpoint, response codes, and parameters are fully aligned.",
                    ))

        logger.info(
            "Comparison complete. Total: %d | Matches: %d | Missing in impl: %d | "
            "Missing in spec: %d | RetCode mismatches: %d | Param mismatches: %d",
            report.total,
            report.matches,
            report.missing_in_impl,
            report.missing_in_spec,
            report.retcode_mismatches,
            report.param_mismatches,
        )
        return report

    def write_report(self, report: DiscrepancyReport, output_path: Path) -> Path:
        """
        Render the DiscrepancyReport as a Markdown file and write it to disk.
        Returns the path of the written file.
        """
        md = self._render_markdown(report)
        output_path.write_text(md, encoding="utf-8")
        logger.info("Discrepancy report written to: %s", output_path)
        return output_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Normalize path for comparison: lowercase, strip trailing slash."""
        return path.rstrip("/").lower()

    @staticmethod
    def _normalize_code(code: str) -> str:
        """Normalize response code: strip whitespace, lowercase 'default'."""
        return code.strip().lower()

    @staticmethod
    def _render_markdown(report: DiscrepancyReport) -> str:
        """Render the discrepancy report as a Markdown string."""
        lines = []

        lines.append("# OpenAPI Spec vs. Implementation — Discrepancy Report")
        lines.append("")
        lines.append(f"**Generated at:** {report.generated_at}  ")
        lines.append(f"**Specification file:** `{report.spec_file}`  ")
        lines.append(f"**Source code directory:** `{report.src_home}`  ")
        lines.append("")

        # Executive summary
        lines.append("## Executive Summary")
        lines.append("")
        lines.append("| Metric | Count |")
        lines.append("|---|---|")
        lines.append(f"| Total endpoints analyzed | {report.total} |")
        lines.append(f"| Fully aligned (MATCH) | {report.matches} |")
        lines.append(f"| Missing in implementation (MISSING_IN_IMPL) | {report.missing_in_impl} |")
        lines.append(f"| Missing in specification (MISSING_IN_SPEC) | {report.missing_in_spec} |")
        lines.append(f"| Response code mismatches (RETCODE_MISMATCH) | {report.retcode_mismatches} |")
        lines.append(f"| Parameter mismatches (PARAM_MISMATCH) | {report.param_mismatches} |")
        lines.append("")

        if not report.has_discrepancies:
            lines.append("> **The specification and implementation are fully aligned. No discrepancies found.**")
            lines.append("")
            return "\n".join(lines)

        # Detailed findings grouped by category
        categories = [
            ("MISSING_IN_IMPL", "Endpoints Declared in Spec but Missing in Implementation"),
            ("MISSING_IN_SPEC", "Endpoints Implemented but Missing in Specification"),
            ("RETCODE_MISMATCH", "Response Code Mismatches"),
            ("PARAM_MISMATCH", "Parameter Mismatches"),
            ("MATCH", "Fully Aligned Endpoints"),
        ]

        for cat_key, cat_title in categories:
            findings = [f for f in report.findings if f.category == cat_key]
            if not findings:
                continue

            lines.append(f"## {cat_title}")
            lines.append("")

            for finding in findings:
                lines.append(f"### `{finding.method} {finding.path}`")
                lines.append("")
                lines.append(f"**Category:** `{finding.category}`  ")

                if finding.spec_codes:
                    lines.append(f"**Spec response codes:** {', '.join(f'`{c}`' for c in finding.spec_codes)}  ")
                if finding.impl_codes:
                    lines.append(f"**Impl response codes:** {', '.join(f'`{c}`' for c in finding.impl_codes)}  ")

                if finding.spec_params:
                    param_names = [f"`{p.get('name', '?')}` ({p.get('in', '?')})" for p in finding.spec_params]
                    lines.append(f"**Spec parameters:** {', '.join(param_names)}  ")
                if finding.impl_params:
                    param_names = [f"`{p.get('name', '?')}` ({p.get('in', '?')})" for p in finding.impl_params]
                    lines.append(f"**Impl parameters:** {', '.join(param_names)}  ")

                if finding.notes:
                    lines.append(f"**Notes:** {finding.notes}  ")

                lines.append("")

        lines.append("---")
        lines.append(f"*Report generated by OpenAPI Spec Improver on {report.generated_at}.*")
        lines.append("")

        return "\n".join(lines)
