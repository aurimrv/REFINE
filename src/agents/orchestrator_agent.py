"""
OrchestratorAgent
-----------------
Coordinates the full OpenAPI Spec Improver pipeline.

Mode A — Spec-only (no --api-src):
  1. Parse the OpenAPI specification.
  2. Enrich each endpoint with realistic examples via LLM.
  3. Write the enriched spec to disk.

Mode B — Spec + Source (--api-src provided):
  1. Parse the OpenAPI specification.
  2. Analyze the source code to extract implemented endpoints/retcodes.
  3. Compare spec vs implementation and generate a Markdown discrepancy report.
  4. Enrich each endpoint using implementation-aware context via LLM.
     (Endpoints present only in the implementation are added to the spec.)
  5. Write the enriched, implementation-aligned spec to disk.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.agents.spec_parser_agent import SpecParserAgent
from src.agents.llm_enrichment_agent import LLMEnrichmentAgent, LLMAuthenticationError
from src.agents.spec_writer_agent import SpecWriterAgent
from src.agents.spec_validator_agent import SpecValidatorAgent
from src.agents.source_analyzer_agent import SourceAnalyzerAgent, ImplementedEndpoint
from src.agents.discrepancy_reporter_agent import DiscrepancyReporterAgent
from src.models.openapi_models import EndpointInfo
from src.utils.config import Config
from src.utils.logger import setup_logger

logger = setup_logger("orchestrator_agent")


class OrchestratorAgent:
    """
    Top-level agent that coordinates all sub-agents to produce an enriched
    OpenAPI specification, and optionally a discrepancy report when source
    code is provided.
    """

    def __init__(
        self,
        spec_path: Path,
        llm_model: Optional[str] = None,
        src_home: Optional[Path] = None,
    ) -> None:
        self.spec_path = spec_path
        self.llm_model = llm_model or Config.LLM_MODEL
        self.src_home = src_home  # None means spec-only mode

    def run(self) -> Tuple[Path, Optional[Path]]:
        """
        Execute the full pipeline.

        Returns:
            (enriched_spec_path, discrepancy_report_path)
            discrepancy_report_path is None when --api-src is not provided.
        """
        # Timestamp shared across all output files of this run
        self._run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        logger.info("=" * 60)
        logger.info("OpenAPI Spec Improver — Starting pipeline")
        logger.info("Spec file : %s", self.spec_path)
        logger.info("LLM model : %s", self.llm_model)
        if self.src_home:
            logger.info("Source dir: %s", self.src_home)
            logger.info("Mode      : Spec + Source Analysis")
        else:
            logger.info("Mode      : Spec-only Enrichment")
        logger.info("=" * 60)

        # ----------------------------------------------------------------
        # Step 1: Parse the OpenAPI specification
        # ----------------------------------------------------------------
        parser = SpecParserAgent(self.spec_path)
        raw_spec = parser.load()
        spec_endpoints: List[EndpointInfo] = parser.parse_endpoints()

        if not spec_endpoints:
            logger.warning("No endpoints found in the specification. Aborting.")
            raise ValueError("No endpoints found in the provided OpenAPI specification.")

        api_info = raw_spec.get("info", {})
        api_context = (
            f"API Title: {api_info.get('title', 'Unknown')}\n"
            f"API Version: {api_info.get('version', 'Unknown')}\n"
            f"Description: {api_info.get('description', 'N/A')}"
        )
        logger.info(
            "Static analysis mode: NO HTTP calls will be made to the API servers "
            "described in the spec. Enrichment is based solely on the spec file content."
        )

        # ----------------------------------------------------------------
        # Step 2 (Mode B only): Analyze source code
        # ----------------------------------------------------------------
        impl_endpoints: List[ImplementedEndpoint] = []
        discrepancy_report_path: Optional[Path] = None
        total_input_tokens = 0
        total_output_tokens = 0

        if self.src_home:
            source_agent = SourceAnalyzerAgent(src_home=self.src_home, model=self.llm_model)
            impl_endpoints = source_agent.analyze()
            src_usage = source_agent.get_token_usage()
            total_input_tokens += src_usage["input_tokens"]
            total_output_tokens += src_usage["output_tokens"]

            if not impl_endpoints:
                logger.warning(
                    "No implemented endpoints were found in the source code. "
                    "Proceeding with spec-only enrichment."
                )

            # ----------------------------------------------------------------
            # Step 3 (Mode B only): Compare spec vs implementation
            # ----------------------------------------------------------------
            reporter = DiscrepancyReporterAgent(
                spec_endpoints=spec_endpoints,
                impl_endpoints=impl_endpoints,
                spec_file=self.spec_path,
                src_home=self.src_home,
            )
            discrepancy_report = reporter.compare()

            # Write the discrepancy report next to the spec file
            spec_stem = self.spec_path.stem
            report_filename = f"{spec_stem}_discrepancy_{self._run_timestamp}.md"
            report_path = self.spec_path.parent / report_filename
            discrepancy_report_path = reporter.write_report(discrepancy_report, report_path)

            logger.info(
                "Discrepancy report: %d finding(s) — "
                "%d match, %d missing in impl, %d missing in spec, "
                "%d retcode mismatch, %d param mismatch.",
                discrepancy_report.total,
                discrepancy_report.matches,
                discrepancy_report.missing_in_impl,
                discrepancy_report.missing_in_spec,
                discrepancy_report.retcode_mismatches,
                discrepancy_report.param_mismatches,
            )

            # Build a lookup: (method, path) → ImplementedEndpoint for retcode resolution
            impl_lookup: Dict[tuple, ImplementedEndpoint] = {
                (ep.method.upper(), ep.path.rstrip("/").lower()): ep
                for ep in impl_endpoints
            }

            # Merge impl-only endpoints into the endpoint list for enrichment
            spec_endpoint_keys = set(impl_lookup.keys())
            for impl_ep in impl_endpoints:
                key = (impl_ep.method.upper(), impl_ep.path.rstrip("/").lower())
                spec_keys = {
                    (ep.method.upper(), ep.path.rstrip("/").lower())
                    for ep in spec_endpoints
                }
                if key not in spec_keys:
                    # Convert ImplementedEndpoint → EndpointInfo for enrichment
                    extra_ep = EndpointInfo(
                        method=impl_ep.method,
                        path=impl_ep.path,
                        operation_id=None,
                        summary=impl_ep.description or f"{impl_ep.method} {impl_ep.path}",
                        description=impl_ep.description,
                        parameters=impl_ep.parameters,
                        request_body=None,
                        responses={code: {} for code in impl_ep.response_codes},
                        response_codes=impl_ep.response_codes,
                    )
                    # Mark as impl-only so SpecWriterAgent inserts it into the paths dict
                    extra_ep._impl_only = True  # type: ignore[attr-defined]
                    spec_endpoints.append(extra_ep)
                    logger.info(
                        "Added impl-only endpoint to enrichment queue: %s %s",
                        impl_ep.method,
                        impl_ep.path,
                    )

            # Align retcodes: replace spec retcodes with impl retcodes for every
            # endpoint where a mismatch exists.  Two sub-cases are handled:
            #
            # Case A — spec uses 'default' as a catch-all:
            #   • impl has explicit error codes beyond 2xx  → replace 'default' with
            #     those codes so the LLM generates targeted examples.
            #   • impl only has 2xx codes                  → keep 'default' as-is.
            #
            # Case B — spec has explicit retcodes (e.g. 200, 401, 403, 404) but
            #   the impl has different explicit codes (e.g. 200, 400):
            #   → replace spec retcodes entirely with impl retcodes so the final
            #     spec is 100% aligned with the implementation.
            for ep in spec_endpoints:
                key = (ep.method.upper(), ep.path.rstrip("/").lower())
                impl_ep = impl_lookup.get(key)
                if not impl_ep:
                    continue

                if "default" in ep.response_codes:
                    # Case A — spec uses 'default': always replace it with the
                    # full list of impl codes (success AND error), so that 201/204
                    # are not silently swallowed and 'default' never leaks through.
                    if impl_ep.response_codes:
                        # All codes that are NOT 'default' from the spec stay;
                        # 'default' is replaced by every code the impl declares.
                        new_codes = [
                            c for c in ep.response_codes if c != "default"
                        ] + list(impl_ep.response_codes)
                        seen_codes: set = set()
                        deduped: List[str] = []
                        for c in new_codes:
                            if c not in seen_codes:
                                deduped.append(c)
                                seen_codes.add(c)
                        old_codes = ep.response_codes[:]
                        ep.response_codes = deduped
                        # Signal SpecWriterAgent to expand 'default' into explicit
                        # entries.  Pass ALL impl codes (including 2xx) so the
                        # writer can create proper response objects for each one.
                        ep._impl_retcodes_replacing_default = list(impl_ep.response_codes)  # type: ignore[attr-defined]
                        logger.info(
                            "[Case A] Resolved 'default' for %s %s: %s → %s",
                            ep.method, ep.path, old_codes, deduped,
                        )
                else:
                    # Case B — spec has explicit retcodes; align with impl
                    spec_codes_set = set(ep.response_codes)
                    impl_codes_set = set(impl_ep.response_codes)
                    if spec_codes_set != impl_codes_set:
                        old_codes = ep.response_codes[:]
                        # Use impl retcodes as the authoritative list
                        ep.response_codes = list(impl_ep.response_codes)
                        # Mark so SpecWriterAgent replaces the responses dict entries
                        ep._impl_retcodes_full_replace = impl_ep.response_codes  # type: ignore[attr-defined]
                        logger.info(
                            "[Case B] Aligned retcodes for %s %s: %s → %s",
                            ep.method, ep.path, old_codes, ep.response_codes,
                        )

            # Extend api_context with implementation notes
            api_context += (
                "\n\nNOTE: Source code analysis has been performed. "
                "Enrich examples to be 100% consistent with the actual implementation. "
                "Use only the response codes and parameters confirmed in the source code."
            )

        # ----------------------------------------------------------------
        # Step 4: Enrich each endpoint via LLM
        # ----------------------------------------------------------------
        # Use the version declared in the spec itself (e.g. "2.0" for Swagger),
        # not the global Config default, so the LLM prompt matches the actual format.
        detected_spec_version = Config.detect_spec_version(raw_spec) or Config.OPENAPI_VERSION
        enrichment_agent = LLMEnrichmentAgent(model=self.llm_model, openapi_version=detected_spec_version)
        enrichments: List[Tuple[EndpointInfo, Dict[str, Any]]] = []

        for idx, endpoint in enumerate(spec_endpoints, start=1):
            logger.info(
                "[%d/%d] Enriching: %s %s",
                idx,
                len(spec_endpoints),
                endpoint.method,
                endpoint.path,
            )
            try:
                examples = enrichment_agent.enrich_endpoint(endpoint, api_context)
                enrichments.append((endpoint, examples))
            except LLMAuthenticationError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Failed to enrich endpoint %s %s: %s. Skipping.",
                    endpoint.method,
                    endpoint.path,
                    exc,
                )
                enrichments.append((endpoint, {
                    "parameters_examples": {},
                    "request_body_examples": {},
                    "response_body_examples": {},
                }))

        # ----------------------------------------------------------------
        # Step 5: Merge and write the enriched spec
        # ----------------------------------------------------------------
        writer = SpecWriterAgent(raw_spec, self.spec_path)
        enriched_spec = writer.merge_examples(enrichments)
        output_path = writer.write(enriched_spec, timestamp=self._run_timestamp)

        # ----------------------------------------------------------------
        # Step 6: Validate and auto-repair the enriched spec
        # ----------------------------------------------------------------
        logger.info(
            "Validating enriched spec against OpenAPI %s schema...",
            Config.OPENAPI_VERSION,
        )
        validator = SpecValidatorAgent(openapi_version=Config.OPENAPI_VERSION)
        repaired_spec, repairs_applied, remaining_errors = validator.validate_and_repair(
            enriched_spec
        )

        if repairs_applied:
            # Overwrite the output file with the repaired version
            import json as _json
            with open(output_path, "w", encoding="utf-8") as _f:
                _json.dump(repaired_spec, _f, indent=2, ensure_ascii=False)
            logger.info(
                "Repaired spec written to: %s (%d auto-repair(s) applied)",
                output_path,
                len(repairs_applied),
            )

        if remaining_errors:
            logger.warning(
                "%d validation error(s) remain after auto-repair. "
                "Manual review required.",
                len(remaining_errors),
            )
        else:
            logger.info(
                "Spec is fully compliant with OpenAPI %s.",
                Config.OPENAPI_VERSION,
            )

        # ----------------------------------------------------------------
        # Step 7: Log token usage
        # ----------------------------------------------------------------
        llm_usage = enrichment_agent.get_token_usage()
        total_input_tokens += llm_usage["input_tokens"]
        total_output_tokens += llm_usage["output_tokens"]
        self._log_token_usage({
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
        })

        logger.info("=" * 60)
        logger.info("Pipeline completed successfully.")
        logger.info("Enriched spec  : %s", output_path)
        if discrepancy_report_path:
            logger.info("Discrepancy rpt: %s", discrepancy_report_path)
        logger.info("OpenAPI version: %s", Config.OPENAPI_VERSION)
        logger.info(
            "Validation     : %s",
            "PASSED" if not remaining_errors else f"{len(remaining_errors)} error(s) remain",
        )
        logger.info(
            "Total tokens   — input: %d, output: %d",
            total_input_tokens,
            total_output_tokens,
        )
        logger.info("=" * 60)

        return output_path, discrepancy_report_path

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _log_token_usage(self, token_usage: Dict[str, int]) -> None:
        """Write token usage statistics to a timestamped CSV file in the spec directory."""
        csv_filename = f"token_usage_{self._run_timestamp}.csv"
        csv_path = self.spec_path.parent / csv_filename
        file_exists = csv_path.exists()

        with open(csv_path, "a", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "timestamp", "spec_file", "src_home", "model",
                "seed", "input_tokens", "output_tokens",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                "timestamp": datetime.now().isoformat(),
                "spec_file": str(self.spec_path),
                "src_home": str(self.src_home) if self.src_home else "",
                "model": self.llm_model,
                "seed": Config.LLM_SEED,
                "input_tokens": token_usage["input_tokens"],
                "output_tokens": token_usage["output_tokens"],
            })

        logger.info("Token usage logged to: %s", csv_path)
