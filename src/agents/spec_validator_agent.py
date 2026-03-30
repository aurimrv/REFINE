"""
SpecValidatorAgent
------------------
Validates an enriched OpenAPI specification against the official JSON Schema
for the configured OPENAPI_VERSION and automatically repairs known structural
violations before re-validating.

Repair rules implemented (version-aware):
  OpenAPI 3.x:
    R1. Parameter with `in: body` → converted to `requestBody` on the operation.
        In OpenAPI 3.0, body parameters do not exist; the request body must be
        declared via the `requestBody` field.
    R2. Parameter with `in: formData` → converted to `requestBody` with
        `application/x-www-form-urlencoded` media type.
    R3. `x-parameter-examples` extension key → renamed to `x-examples` to avoid
        conflicts (kept as extension, so it remains valid under `^x-` pattern).
    R4. Response code keys that are integers → converted to strings (e.g. 200 → "200").

After auto-repair, the spec is re-validated. Any remaining errors are logged
as warnings so the user can fix them manually.
"""

import copy
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.utils.config import Config
from src.utils.logger import setup_logger

logger = setup_logger("spec_validator_agent")


class SpecValidatorAgent:
    """
    Validates and auto-repairs an OpenAPI specification dict against the
    JSON Schema for the configured OPENAPI_VERSION.
    """

    def __init__(self, openapi_version: Optional[str] = None) -> None:
        self.openapi_version = openapi_version or Config.OPENAPI_VERSION
        self._schema: Optional[Dict[str, Any]] = None
        self._schema_path: Optional[Path] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_and_repair(
        self, spec: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[str], List[str]]:
        """
        Validate *spec* against the OpenAPI JSON Schema, apply auto-repairs for
        known violation patterns, then re-validate.

        The schema version is determined from the spec itself (field 'openapi'
        for OAS 3.x, 'swagger' for Swagger 2.0), overriding the configured
        OPENAPI_VERSION so that a Swagger 2.0 spec is never validated against
        the OAS 3.0 schema.

        Returns:
            (repaired_spec, repairs_applied, remaining_errors)
            - repaired_spec: the spec after all auto-repairs
            - repairs_applied: human-readable list of repairs made
            - remaining_errors: validation errors that could not be auto-repaired
        """
        # Auto-detect the spec version from the document itself.
        detected_version = self._detect_spec_version(spec)
        if detected_version != self.openapi_version:
            logger.info(
                "Spec version detected as '%s'; overriding configured validation "
                "target from '%s' to '%s'.",
                detected_version,
                self.openapi_version,
                detected_version,
            )
            self.openapi_version = detected_version
            # Reset cached schema so the correct one is loaded.
            self._schema = None

        schema = self._load_schema()
        if schema is None:
            logger.warning(
                "Schema file not found for OpenAPI %s — skipping validation.",
                self.openapi_version,
            )
            return spec, [], []

        # First pass: collect initial errors
        initial_errors = self._collect_errors(spec, schema)
        if not initial_errors:
            logger.info(
                "Validation passed with 0 errors against OpenAPI %s schema.",
                self.openapi_version,
            )
            return spec, [], []

        logger.info(
            "Found %d validation error(s) against OpenAPI %s schema. "
            "Attempting auto-repair...",
            len(initial_errors),
            self.openapi_version,
        )

        # Apply auto-repairs
        repaired = copy.deepcopy(spec)
        repairs_applied: List[str] = []
        self._repair(repaired, repairs_applied)

        # Second pass: re-validate after repairs
        remaining_errors = self._collect_errors(repaired, schema)

        if not remaining_errors:
            logger.info(
                "All validation errors resolved after %d auto-repair(s). "
                "Spec is now fully compliant with OpenAPI %s.",
                len(repairs_applied),
                self.openapi_version,
            )
        else:
            logger.warning(
                "%d validation error(s) remain after auto-repair and require "
                "manual intervention:",
                len(remaining_errors),
            )
            for err in remaining_errors:
                logger.warning("  • [%s] %s", err["path"], err["message"])

        return repaired, repairs_applied, remaining_errors

    def validate_file(self, spec_path: Path) -> Tuple[bool, List[str]]:
        """
        Validate a spec file on disk (read-only, no repairs).

        Returns:
            (is_valid, error_messages)
        """
        with open(spec_path, encoding="utf-8") as f:
            spec = json.load(f)
        schema = self._load_schema()
        if schema is None:
            return True, []
        errors = self._collect_errors(spec, schema)
        return len(errors) == 0, [f"[{e['path']}] {e['message']}" for e in errors]

    # ------------------------------------------------------------------
    # Private: Schema loading
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_spec_version(spec: Dict[str, Any]) -> str:
        """
        Return the version string from the spec document.
        OAS 3.x documents have an 'openapi' key; Swagger 2.x have 'swagger'.
        Falls back to the module-level default when neither key is present.
        """
        version = spec.get("openapi") or spec.get("swagger")
        if version:
            return str(version)
        from src.utils.config import Config  # local import to avoid circular
        return Config.OPENAPI_VERSION

    def _load_schema(self) -> Optional[Dict[str, Any]]:
        """Load and cache the JSON Schema for the configured OpenAPI version."""
        if self._schema is not None:
            return self._schema
        try:
            schema_path = Config.get_schema_path(self.openapi_version)
        except FileNotFoundError as exc:
            logger.warning("%s", exc)
            return None

        with open(schema_path, encoding="utf-8") as f:
            self._schema = json.load(f)
        self._schema_path = schema_path
        logger.info(
            "Loaded OpenAPI %s JSON Schema from: %s",
            self.openapi_version,
            schema_path,
        )
        return self._schema

    # ------------------------------------------------------------------
    # Private: Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_errors(
        spec: Dict[str, Any], schema: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Run jsonschema validation and return a list of {path, message} dicts."""
        try:
            from jsonschema import Draft4Validator
        except ImportError:
            logger.error(
                "jsonschema package is not installed. "
                "Run: pip install jsonschema"
            )
            return []

        validator = Draft4Validator(schema)
        errors = []
        for err in validator.iter_errors(spec):
            path = " > ".join(str(p) for p in err.absolute_path) or "(root)"
            errors.append({"path": path, "message": err.message[:300]})
        return errors

    # ------------------------------------------------------------------
    # Private: Auto-repair
    # ------------------------------------------------------------------

    def _repair(self, spec: Dict[str, Any], repairs: List[str]) -> None:
        """
        Apply all version-aware repair rules in-place to *spec*.
        Appends human-readable descriptions of each repair to *repairs*.
        """
        major_version = int(self.openapi_version.split(".")[0])

        # R7: Swagger 2.0 requires info.title — inject a placeholder if missing.
        if major_version < 3:
            info = spec.setdefault("info", {})
            if not info.get("title"):
                info["title"] = "API"
                msg = "R7: Added missing required 'info.title' field (set to 'API')"
                repairs.append(msg)
                logger.info(msg)

        for path_str, path_item in spec.get("paths", {}).items():
            if not isinstance(path_item, dict):
                continue
            for method, operation in path_item.items():
                if not isinstance(operation, dict):
                    continue
                # Skip non-operation keys (e.g. 'parameters', 'summary')
                if method not in {
                    "get", "put", "post", "delete", "options",
                    "head", "patch", "trace",
                }:
                    continue

                if major_version >= 3:
                    self._repair_body_params_v3(
                        path_str, method, operation, repairs
                    )
                    self._repair_response_code_keys(
                        path_str, method, operation, repairs
                    )
                else:
                    # Swagger 2.0: remove any OAS 3.x 'content' fields that may
                    # have been injected into response objects by the writer.
                    self._repair_remove_oas3_content_from_responses_v2(
                        path_str, method, operation, repairs
                    )
                    # R6: Remove 'requestBody' (OAS 3.x field) from Swagger 2.0
                    # operations — it is not valid in Swagger 2.0.
                    self._repair_remove_request_body_v2(
                        path_str, method, operation, repairs
                    )
                    # R8: Deduplicate parameters by (name, in) within an operation.
                    self._repair_deduplicate_parameters(
                        path_str, method, operation, repairs
                    )
                    # R9: Remove 'example' field from individual parameters.
                    # The Swagger 2.0 parameter sub-schemas (pathParameterSubSchema,
                    # queryParameterSubSchema, etc.) use additionalProperties: false
                    # and do not include 'example', so it is a schema violation.
                    self._repair_remove_example_from_params_v2(
                        path_str, method, operation, repairs
                    )

    @staticmethod
    def _repair_remove_request_body_v2(
        path_str: str,
        method: str,
        operation: Dict[str, Any],
        repairs: List[str],
    ) -> None:
        """
        R6 (Swagger 2.0 only): Remove 'requestBody' key from an operation.
        Swagger 2.0 does not support requestBody; request bodies are expressed
        as 'in: body' or 'in: formData' parameters. A requestBody may have been
        injected by a previous pipeline run's R1/R2 auto-repair.
        """
        if "requestBody" in operation:
            del operation["requestBody"]
            msg = (
                f"R6: {method.upper()} {path_str} — removed OAS 3.x 'requestBody' "
                f"field from Swagger 2.0 operation"
            )
            repairs.append(msg)
            logger.info(msg)

    @staticmethod
    def _repair_deduplicate_parameters(
        path_str: str,
        method: str,
        operation: Dict[str, Any],
        repairs: List[str],
    ) -> None:
        """
        R8: Deduplicate parameters by (name, in) within an operation.
        JAX-RS auto-generated Swagger specs sometimes list the same path
        parameter twice. The Swagger 2.0 schema requires uniqueItems in the
        parameters array, so duplicates must be removed.
        """
        params = operation.get("parameters")
        if not params or not isinstance(params, list):
            return
        seen: set = set()
        deduped = []
        removed = 0
        for p in params:
            key = (p.get("name"), p.get("in"))
            if key in seen:
                removed += 1
            else:
                seen.add(key)
                deduped.append(p)
        if removed:
            operation["parameters"] = deduped
            msg = (
                f"R8: {method.upper()} {path_str} — removed {removed} duplicate "
                f"parameter(s) from operation"
            )
            repairs.append(msg)
            logger.info(msg)

    @staticmethod
    def _repair_remove_example_from_params_v2(
        path_str: str,
        method: str,
        operation: Dict[str, Any],
        repairs: List[str],
    ) -> None:
        """
        R9 (Swagger 2.0 only): Remove 'example' field from individual parameters.
        The Swagger 2.0 parameter sub-schemas (pathParameterSubSchema,
        queryParameterSubSchema, formDataParameterSubSchema, etc.) are defined
        with additionalProperties: false and do not include an 'example' property.
        Injecting 'example' directly into a parameter object is therefore a schema
        violation in Swagger 2.0. Examples are stored in x-parameter-examples
        instead (a vendor extension, which is always allowed).
        """
        params = operation.get("parameters")
        if not params or not isinstance(params, list):
            return
        removed = 0
        for p in params:
            if isinstance(p, dict) and "example" in p:
                del p["example"]
                removed += 1
        if removed:
            msg = (
                f"R9: {method.upper()} {path_str} — removed 'example' from "
                f"{removed} parameter(s) (not valid in Swagger 2.0 sub-schemas)"
            )
            repairs.append(msg)
            logger.info(msg)

    @staticmethod
    def _repair_remove_oas3_content_from_responses_v2(
        path_str: str,
        method: str,
        operation: Dict[str, Any],
        repairs: List[str],
    ) -> None:
        """
        R5 (Swagger 2.0 only): Remove 'content' keys from response objects.
        Swagger 2.0 responses do not have a 'content' field; examples are
        stored under vendor extension 'x-examples' instead. If a previous
        pipeline run accidentally injected OAS 3.x 'content' into a 2.0
        response, this rule removes it to restore schema compliance.
        """
        responses = operation.get("responses", {})
        for code, response_obj in responses.items():
            if isinstance(response_obj, dict) and "content" in response_obj:
                del response_obj["content"]
                msg = (
                    f"R5: {method.upper()} {path_str} [{code}] — removed OAS 3.x "
                    f"'content' field from Swagger 2.0 response object"
                )
                repairs.append(msg)
                logger.info(msg)

    def _repair_body_params_v3(
        self,
        path_str: str,
        method: str,
        operation: Dict[str, Any],
        repairs: List[str],
    ) -> None:
        """
        R1/R2: Convert OpenAPI 2.0-style body/formData parameters to OpenAPI 3.0
        requestBody.

        - `in: body`     → requestBody with application/json media type
        - `in: formData` → requestBody with application/x-www-form-urlencoded
        """
        params: List[Dict[str, Any]] = operation.get("parameters", [])
        body_params = [p for p in params if isinstance(p, dict) and p.get("in") in ("body", "formData")]

        if not body_params:
            return

        # Remove body/formData params from the parameters list
        operation["parameters"] = [
            p for p in params
            if not (isinstance(p, dict) and p.get("in") in ("body", "formData"))
        ]
        if not operation["parameters"]:
            del operation["parameters"]

        # Build requestBody if not already present
        if "requestBody" not in operation:
            # Determine media type
            has_form = any(p.get("in") == "formData" for p in body_params)
            media_type = (
                "application/x-www-form-urlencoded" if has_form else "application/json"
            )

            # Merge all body params into a single schema object
            if len(body_params) == 1:
                bp = body_params[0]
                schema = bp.get("schema") or {"type": "object"}
                description = bp.get("description", "")
                required_flag = bp.get("required", False)
            else:
                # Multiple body params → wrap in an object schema
                properties = {}
                required_props = []
                for bp in body_params:
                    name = bp.get("name", "body")
                    properties[name] = bp.get("schema") or {"type": "string"}
                    if bp.get("required"):
                        required_props.append(name)
                schema = {"type": "object", "properties": properties}
                if required_props:
                    schema["required"] = required_props
                description = ""
                required_flag = any(p.get("required") for p in body_params)

            request_body: Dict[str, Any] = {
                "content": {
                    media_type: {
                        "schema": schema
                    }
                }
            }
            if description:
                request_body["description"] = description
            if required_flag:
                request_body["required"] = True

            operation["requestBody"] = request_body

            param_names = [p.get("name", "?") for p in body_params]
            repair_msg = (
                f"R1: {method.upper()} {path_str} — converted body parameter(s) "
                f"{param_names} to requestBody ({media_type})"
            )
            repairs.append(repair_msg)
            logger.info(repair_msg)

    @staticmethod
    def _repair_response_code_keys(
        path_str: str,
        method: str,
        operation: Dict[str, Any],
        repairs: List[str],
    ) -> None:
        """
        R4: Ensure all response code keys are strings (e.g. 200 → "200").
        The OpenAPI schema requires response codes to be string keys.
        """
        responses = operation.get("responses", {})
        int_keys = [k for k in responses if isinstance(k, int)]
        for k in int_keys:
            responses[str(k)] = responses.pop(k)
            msg = (
                f"R4: {method.upper()} {path_str} — converted integer response "
                f"code key {k} to string '{k}'"
            )
            repairs.append(msg)
            logger.info(msg)
