"""
SpecParserAgent
---------------
Responsible for loading and parsing an OpenAPI specification file,
extracting all endpoints, HTTP methods, parameters, request bodies,
and response codes into structured EndpointInfo objects.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from src.models.openapi_models import EndpointInfo
from src.utils.logger import setup_logger

logger = setup_logger("spec_parser_agent")

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


class SpecParserAgent:
    """
    Agent that parses an OpenAPI 2.x/3.x specification file and extracts
    structured information about every endpoint.
    """

    def __init__(self, spec_path: Path) -> None:
        self.spec_path = spec_path
        self.raw_spec: Dict[str, Any] = {}
        # Populated by load(): "2.0", "3.0.x", "3.1.x", etc.
        self.spec_version: str = ""
        # Major version integer: 2 or 3
        self.spec_major_version: int = 3

    def load(self) -> Dict[str, Any]:
        """Load the OpenAPI JSON file from disk and return the raw dict."""
        logger.info("Loading OpenAPI specification from: %s", self.spec_path)
        with open(self.spec_path, "r", encoding="utf-8") as f:
            self.raw_spec = json.load(f)

        # Detect version: OAS 3.x uses "openapi", Swagger 2.x uses "swagger"
        raw_version = self.raw_spec.get("openapi") or self.raw_spec.get("swagger", "unknown")
        self.spec_version = str(raw_version)
        try:
            self.spec_major_version = int(self.spec_version.split(".")[0])
        except (ValueError, IndexError):
            self.spec_major_version = 3

        title = self.raw_spec.get("info", {}).get("title", "Unknown API")
        servers = self.raw_spec.get("servers", [])
        server_urls = [s.get("url", "") for s in servers]
        logger.info("Loaded spec: '%s' (OpenAPI %s)", title, self.spec_version)
        if self.spec_major_version == 2:
            logger.info(
                "Detected Swagger/OpenAPI 2.0 specification. "
                "Pipeline will operate in Swagger 2.0 compatibility mode."
            )
        if server_urls:
            logger.info(
                "Spec declares server(s): %s — these will NOT be contacted. "
                "Enrichment is performed via static analysis only.",
                server_urls,
            )
        return self.raw_spec

    def get_spec_version(self) -> str:
        """Return the raw version string detected from the spec (e.g. '2.0', '3.0.3')."""
        return self.spec_version

    def parse_endpoints(self) -> List[EndpointInfo]:
        """
        Traverse the 'paths' section of the spec and return a list of
        EndpointInfo objects, one per (path, method) combination.
        """
        if not self.raw_spec:
            self.load()

        paths: Dict[str, Any] = self.raw_spec.get("paths", {})
        endpoints: List[EndpointInfo] = []

        for path, path_item in paths.items():
            # Path-level parameters shared by all methods
            path_level_params: List[Dict[str, Any]] = path_item.get("parameters", [])

            for method, operation in path_item.items():
                if method.lower() not in HTTP_METHODS:
                    continue
                if not isinstance(operation, dict):
                    continue

                # Merge path-level and operation-level parameters,
                # deduplicating by (name, in) to fix specs that list the same
                # path parameter twice (common in JAX-RS auto-generated specs).
                op_params: List[Dict[str, Any]] = operation.get("parameters", [])
                merged_params = _merge_parameters(path_level_params, op_params)

                responses: Dict[str, Any] = operation.get("responses", {})
                response_codes = list(responses.keys())

                endpoint = EndpointInfo(
                    path=path,
                    method=method.upper(),
                    operation_id=operation.get("operationId"),
                    summary=operation.get("summary"),
                    description=operation.get("description"),
                    parameters=merged_params,
                    request_body=operation.get("requestBody"),
                    response_codes=response_codes,
                    responses=responses,
                )
                endpoints.append(endpoint)
                logger.debug(
                    "Parsed endpoint: %s %s (responses: %s)",
                    method.upper(),
                    path,
                    response_codes,
                )

        logger.info("Total endpoints parsed: %d", len(endpoints))
        return endpoints


def _merge_parameters(
    path_params: List[Dict[str, Any]], op_params: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Merge path-level and operation-level parameters.
    Operation-level parameters override path-level ones with the same name+in.
    """
    merged: Dict[tuple, Dict[str, Any]] = {}
    for param in path_params:
        key = (param.get("name"), param.get("in"))
        merged[key] = param
    for param in op_params:
        key = (param.get("name"), param.get("in"))
        merged[key] = param
    return list(merged.values())
