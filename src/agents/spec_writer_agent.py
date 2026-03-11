"""
SpecWriterAgent
---------------
Responsible for merging the LLM-generated examples back into the original
OpenAPI specification and writing the enriched spec to a new JSON file.
The output file is saved in the same directory as the original, with a
timestamp suffix appended to the original filename.
"""

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.models.openapi_models import EndpointInfo
from src.utils.logger import setup_logger

logger = setup_logger("spec_writer_agent")


class SpecWriterAgent:
    """
    Agent that merges enrichment data into the original OpenAPI spec
    and persists the improved specification to disk.
    """

    def __init__(self, original_spec: Dict[str, Any], spec_path: Path) -> None:
        self.original_spec = original_spec
        self.spec_path = spec_path

    def merge_examples(
        self,
        enrichments: List[Tuple[EndpointInfo, Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """
        Deep-copy the original spec and inject examples from the enrichment data.

        For each (endpoint, examples) pair:
        - Adds 'example' fields to parameters.
        - Adds 'examples' to request body content (if present).
        - Adds 'examples' to each response object.
        - When the endpoint has _impl_retcodes_replacing_default set, expands the
          'default' response entry into individual entries for each real retcode.

        Returns the enriched spec dict.
        """
        enriched = copy.deepcopy(self.original_spec)
        paths = enriched.get("paths", {})

        for endpoint, examples in enrichments:
            path = endpoint.path
            method = endpoint.method.lower()

            if path not in paths:
                logger.warning("Path '%s' not found in spec during merge. Skipping.", path)
                continue

            operation: Dict[str, Any] = paths[path].get(method, {})
            if not operation:
                logger.warning(
                    "Method '%s' not found for path '%s' during merge. Skipping.",
                    method,
                    path,
                )
                continue

            param_examples: Dict[str, Any] = examples.get("parameters_examples", {})
            req_body_examples: Dict[str, Any] = examples.get("request_body_examples", {})
            response_body_examples: Dict[str, Any] = examples.get("response_body_examples", {})

            # ---- Expand 'default' into real retcodes (when impl provides them) ----
            # If the OrchestratorAgent resolved 'default' → real codes, expand the
            # responses dict in the spec: remove 'default' and add one entry per
            # real code, copying the original 'default' response object as template.
            impl_retcodes: List[str] = getattr(
                endpoint, "_impl_retcodes_replacing_default", []
            )
            responses: Dict[str, Any] = operation.get("responses", {})
            if impl_retcodes and "default" in responses:
                default_template = copy.deepcopy(responses["default"])
                del responses["default"]
                for real_code in impl_retcodes:
                    if real_code not in responses:
                        # Build a sensible description from the HTTP code
                        code_int = int(real_code) if real_code.isdigit() else 0
                        if 400 <= code_int < 500:
                            desc = f"Client error — {real_code}"
                        elif 500 <= code_int < 600:
                            desc = f"Server error — {real_code}"
                        else:
                            desc = default_template.get("description", real_code)
                        new_entry = copy.deepcopy(default_template)
                        new_entry["description"] = desc
                        responses[real_code] = new_entry
                        logger.debug(
                            "Expanded 'default' → '%s' for %s %s",
                            real_code, endpoint.method, endpoint.path,
                        )
                logger.info(
                    "Replaced 'default' with explicit codes %s for %s %s",
                    impl_retcodes, endpoint.method, endpoint.path,
                )

            # ---- Enrich parameters ----
            if param_examples and operation.get("parameters"):
                # Use the first response code's examples as the canonical parameter example
                first_code = next(iter(param_examples), None)
                if first_code:
                    code_param_examples = param_examples[first_code]
                    for param in operation["parameters"]:
                        param_name = param.get("name")
                        if param_name and param_name in code_param_examples:
                            param["example"] = code_param_examples[param_name]

                # Also add per-response-code parameter examples under x-examples
                operation["x-parameter-examples"] = param_examples

            # ---- Enrich request body ----
            if req_body_examples and operation.get("requestBody"):
                content = operation["requestBody"].get("content", {})
                for media_type, media_obj in content.items():
                    if isinstance(media_obj, dict):
                        media_obj["examples"] = {
                            f"example_{code}": {"value": val}
                            for code, val in req_body_examples.items()
                            if val
                        }

            # ---- Enrich responses ----
            for code, response_obj in responses.items():
                if not isinstance(response_obj, dict):
                    continue
                example_value = response_body_examples.get(str(code))
                if example_value is None:
                    # Try "default" key as fallback for codes that were not explicitly
                    # generated (e.g., when 'default' was kept as-is in spec-only mode)
                    example_value = response_body_examples.get("default")

                if example_value is not None:
                    # Inject into existing content or create a new content block
                    content = response_obj.get("content")
                    if content:
                        for media_type, media_obj in content.items():
                            if isinstance(media_obj, dict):
                                media_obj["examples"] = {
                                    f"example_{code}": {"value": example_value}
                                }
                    else:
                        # No content block defined; add one with application/json
                        response_obj["content"] = {
                            "application/json": {
                                "examples": {
                                    f"example_{code}": {"value": example_value}
                                }
                            }
                        }

            logger.debug(
                "Merged examples for endpoint: %s %s", endpoint.method, endpoint.path
            )

        logger.info("All enrichments merged into the specification.")
        return enriched

    def write(self, enriched_spec: Dict[str, Any], timestamp: Optional[str] = None) -> Path:
        """
        Write the enriched spec to a new file in the same directory as the original.
        The filename follows the pattern: <original_stem>_<timestamp>.json

        If `timestamp` is provided, it is used as-is; otherwise a new timestamp
        is generated. Passing a shared timestamp ensures all output files of the
        same run (spec, discrepancy report, token usage CSV) share the same suffix.

        Returns the path to the written file.
        """
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_filename = f"{self.spec_path.stem}_{timestamp}.json"
        output_path = self.spec_path.parent / output_filename

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(enriched_spec, f, indent=2, ensure_ascii=False)

        logger.info("Enriched specification written to: %s", output_path)
        return output_path
