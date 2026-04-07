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
    Agent that parses an OpenAPI 3.x specification file and extracts
    structured information about every endpoint.
    """

    def __init__(self, spec_path: Path) -> None:
        self.spec_path = spec_path
        self.raw_spec: Dict[str, Any] = {}

    def load(self) -> Dict[str, Any]:
        """Load the OpenAPI JSON file from disk and return the raw dict."""
        logger.info("Loading OpenAPI specification from: %s", self.spec_path)
        with open(self.spec_path, "r", encoding="utf-8") as f:
            self.raw_spec = json.load(f)
        version = self.raw_spec.get("openapi", self.raw_spec.get("swagger", "unknown"))
        title = self.raw_spec.get("info", {}).get("title", "Unknown API")
        servers = self.raw_spec.get("servers", [])
        server_urls = [s.get("url", "") for s in servers]
        logger.info("Loaded spec: '%s' (OpenAPI %s)", title, version)
        if server_urls:
            logger.info(
                "Spec declares server(s): %s — these will NOT be contacted. "
                "Enrichment is performed via static analysis only.",
                server_urls,
            )

        # Derive the base path prefix used by the spec so callers can strip it
        # from impl-extracted paths before comparison.
        #
        # Swagger 2.0: explicit 'basePath' field (e.g. "/rest").
        # OpenAPI 3.x: path component of the first server URL
        #              (e.g. "http://localhost:8080/rest" → "/rest").
        #
        # The prefix is normalised to lowercase with no trailing slash so it
        # can be compared directly against lowercased impl paths.
        self.spec_base_path: str = self._extract_base_path(self.raw_spec)
        if self.spec_base_path:
            logger.info(
                "Spec base path detected: '%s' — will be stripped from impl paths "
                "during comparison to align path formats.",
                self.spec_base_path,
            )
        return self.raw_spec

    @staticmethod
    def _extract_base_path(spec: Dict[str, Any]) -> str:
        """
        Return the URL path prefix declared in the spec, normalised to
        lowercase with no trailing slash.  Returns '' if no prefix is found
        or if the prefix is just '/'.
        """
        from urllib.parse import urlparse

        # Swagger 2.0
        base = spec.get("basePath", "")
        if not base:
            # OpenAPI 3.x — take the path component of the first server URL
            servers = spec.get("servers", [])
            if servers:
                url = servers[0].get("url", "")
                base = urlparse(url).path if url else ""

        base = base.rstrip("/").lower()
        return base if base and base != "/" else ""

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

                # Merge path-level and operation-level parameters
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
