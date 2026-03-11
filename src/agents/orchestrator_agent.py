"""
OrchestratorAgent
-----------------
Coordinates the multi-agent pipeline:
  1. SpecParserAgent  — loads and parses the OpenAPI specification.
  2. LLMEnrichmentAgent — calls the LLM to generate examples per endpoint.
  3. SpecWriterAgent  — merges examples and writes the enriched spec to disk.

Also tracks and logs overall token usage.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.agents.spec_parser_agent import SpecParserAgent
from src.agents.llm_enrichment_agent import LLMEnrichmentAgent
from src.agents.spec_writer_agent import SpecWriterAgent
from src.models.openapi_models import EndpointInfo
from src.utils.config import Config
from src.utils.logger import setup_logger

logger = setup_logger("orchestrator_agent")


class OrchestratorAgent:
    """
    Top-level agent that orchestrates the full OpenAPI enrichment pipeline.
    """

    def __init__(self, spec_path: Path, llm_model: Optional[str] = None) -> None:
        self.spec_path = spec_path
        self.llm_model = llm_model or Config.LLM_MODEL

    def run(self) -> Path:
        """
        Execute the full enrichment pipeline and return the path to the output file.
        """
        logger.info("=" * 60)
        logger.info("OpenAPI Spec Improver — Starting pipeline")
        logger.info("Spec file : %s", self.spec_path)
        logger.info("LLM model : %s", self.llm_model)
        logger.info("=" * 60)

        # --- Step 1: Parse the specification ---
        parser = SpecParserAgent(self.spec_path)
        raw_spec = parser.load()
        endpoints: List[EndpointInfo] = parser.parse_endpoints()

        if not endpoints:
            logger.warning("No endpoints found in the specification. Aborting.")
            raise ValueError("No endpoints found in the provided OpenAPI specification.")

        # Build a short API context description for the LLM
        api_info = raw_spec.get("info", {})
        api_context = (
            f"API Title: {api_info.get('title', 'Unknown')}\n"
            f"API Version: {api_info.get('version', 'Unknown')}\n"
            f"Description: {api_info.get('description', 'N/A')}"
        )

        # --- Step 2: Enrich each endpoint via LLM ---
        enrichment_agent = LLMEnrichmentAgent(model=self.llm_model)
        enrichments: List[Tuple[EndpointInfo, Dict[str, Any]]] = []

        for idx, endpoint in enumerate(endpoints, start=1):
            logger.info(
                "[%d/%d] Enriching: %s %s",
                idx,
                len(endpoints),
                endpoint.method,
                endpoint.path,
            )
            try:
                examples = enrichment_agent.enrich_endpoint(endpoint, api_context)
                enrichments.append((endpoint, examples))
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Failed to enrich endpoint %s %s: %s. Skipping.",
                    endpoint.method,
                    endpoint.path,
                    exc,
                )
                # Append empty examples so the endpoint is still present in output
                enrichments.append((endpoint, {
                    "parameters_examples": {},
                    "request_body_examples": {},
                    "response_body_examples": {},
                }))

        # --- Step 3: Merge and write the enriched spec ---
        writer = SpecWriterAgent(raw_spec, self.spec_path)
        enriched_spec = writer.merge_examples(enrichments)
        output_path = writer.write(enriched_spec)

        # --- Step 4: Log token usage ---
        token_usage = enrichment_agent.get_token_usage()
        self._log_token_usage(token_usage)

        logger.info("=" * 60)
        logger.info("Pipeline completed successfully.")
        logger.info("Output file: %s", output_path)
        logger.info(
            "Total tokens — input: %d, output: %d",
            token_usage["input_tokens"],
            token_usage["output_tokens"],
        )
        logger.info("=" * 60)

        return output_path

    def _log_token_usage(self, token_usage: Dict[str, int]) -> None:
        """
        Append token usage statistics to a CSV file in the project root.
        The CSV filename includes the LLM seed for traceability.
        """
        csv_filename = f"token_usage_seed_{Config.LLM_SEED}.csv"
        csv_path = Path(csv_filename)
        file_exists = csv_path.exists()

        with open(csv_path, "a", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["timestamp", "spec_file", "model", "seed", "input_tokens", "output_tokens"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                "timestamp": datetime.now().isoformat(),
                "spec_file": str(self.spec_path),
                "model": self.llm_model,
                "seed": Config.LLM_SEED,
                "input_tokens": token_usage["input_tokens"],
                "output_tokens": token_usage["output_tokens"],
            })
        logger.info("Token usage logged to: %s", csv_path)
