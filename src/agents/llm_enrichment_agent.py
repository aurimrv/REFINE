"""
LLMEnrichmentAgent
------------------
Responsible for calling the LLM (via OpenAI-compatible API) to generate
realistic examples for each endpoint and response code in the OpenAPI spec.

For each endpoint/retcode pair, the agent generates MULTIPLE named examples:
  - Success codes (2xx): at least 2 examples covering typical and edge cases.
  - Error codes (4xx/5xx): at least 3 examples, including variations that use
    wrong data types (e.g. string where integer is expected), boundary values
    (zero, negative, very large), and null/missing values — to maximize the
    chance of actually triggering the error when the endpoint is called.

Uses retry logic and rate limiting to handle transient API errors gracefully.
Non-retriable errors (401 Unauthorized, 403 Forbidden) cause an immediate
failure with a clear diagnostic message rather than wasting retry attempts.
"""

import json
from typing import Any, Dict, Optional

from openai import OpenAI, AuthenticationError, PermissionDeniedError
from openai import APIStatusError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_not_exception_type,
)

from src.models.openapi_models import EndpointInfo
from src.utils.config import Config
from src.utils.logger import setup_logger
from src.utils.rate_limiter import RateLimiter

logger = setup_logger("llm_enrichment_agent")

# HTTP status codes that should NOT be retried — they indicate a permanent
# configuration problem (wrong/missing API key, insufficient permissions, etc.)
NON_RETRIABLE_STATUS_CODES = {401, 403}


def _build_system_prompt(openapi_version: str) -> str:
    """
    Build the system prompt for the LLM, embedding the target OpenAPI version
    so the model generates structurally compatible output from the start.
    """
    major = int(openapi_version.split(".")[0])

    if major >= 3:
        body_param_rule = (
            f"- OpenAPI {openapi_version} DOES NOT support 'in: body' or 'in: formData' "
            "parameters. Request bodies MUST be declared as 'requestBody' on the operation, "
            "NOT as a parameter. If the endpoint accepts a request body, include it in "
            "'request_body_examples' only."
        )
        param_locations = "path, query, header, or cookie"
    else:
        body_param_rule = (
            f"- OpenAPI {openapi_version}: request bodies are declared as parameters "
            "with 'in: body'. Include body examples in 'request_body_examples'."
        )
        param_locations = "path, query, header, cookie, or body"

    return f"""You are an expert API documentation engineer specializing in OpenAPI Specification {openapi_version}.
Your task is to enrich an OpenAPI endpoint definition by adding realistic, clear, and meaningful examples.

Target OpenAPI version: {openapi_version}

IMPORTANT: You must generate ALL examples purely by inference from the endpoint definition.
Do NOT attempt to call, connect to, or access the API server in any way.
The API server may not be running — this is a static documentation enrichment task.

For EACH response code of the endpoint, you must generate MULTIPLE named examples:

For SUCCESS codes (2xx):
  - Generate at least 2 named examples.
  - "typical": realistic, representative values that would normally succeed.
  - "edge_case": boundary or unusual but still valid values (e.g. minimum valid value, maximum valid value, empty list, single-item list).

For ERROR codes (4xx/5xx):
  - Generate at least 3 named examples, each designed to actually trigger the error.
  - Use DIFFERENT strategies per example to maximize coverage:
    a) "invalid_type": use a value of the WRONG data type (e.g. a string like "abc" where an integer is expected, or a boolean where a number is expected).
    b) "boundary_violation": use a value that violates a numeric boundary (e.g. negative number, zero when positive is required, value exceeding maximum).
    c) "null_or_missing": use null or an empty string for a required parameter.
  - These examples are intentionally invalid — they SHOULD cause the error response.

OpenAPI {openapi_version} compatibility rules (STRICTLY FOLLOW):
{body_param_rule}
- Parameter 'in' field MUST be one of: {param_locations}.
- Response code keys MUST be strings (e.g. "200", "404"), never integers.
- Do NOT add fields that are not part of the OpenAPI {openapi_version} specification.
- Use realistic data (real country names, valid ISO codes, real currencies, etc.) — NOT placeholder values like "string" or "example".
- CRITICAL: Generate examples ONLY for the response codes explicitly listed in the endpoint definition provided in the user message. Do NOT add examples for any other response codes (e.g. do NOT add 401, 403, 404 if they are not listed). The response code keys in "parameters_examples", "request_body_examples", and "response_body_examples" MUST be an exact subset of the codes listed under "Response codes to cover".
- Return ONLY a valid JSON object. Do NOT include markdown code fences or any extra text.
- The JSON must follow this EXACT structure:

{{
  "parameters_examples": {{
    "<response_code>": [
      {{
        "_name": "<example_name>",
        "<param_name>": <example_value>,
        "<param_name2>": <example_value2>
      }},
      {{
        "_name": "<another_example_name>",
        "<param_name>": <example_value>,
        "<param_name2>": <example_value2>
      }}
    ]
  }},
  "request_body_examples": {{
    "<response_code>": [
      {{
        "_name": "<example_name>",
        "value": {{ ... }}
      }}
    ]
  }},
  "response_body_examples": {{
    "<response_code>": {{ ... }}
  }}
}}

IMPORTANT NOTES on the structure:
- "parameters_examples" maps each response code to a LIST of example objects.
- Each example object MUST have a "_name" field (string) identifying the example.
- The remaining fields in each example object are the parameter name-value pairs.
- "request_body_examples" maps each response code to a LIST of example objects, each with "_name" and "value".
- "response_body_examples" maps each response code to a SINGLE representative response body object (not a list).
- If the endpoint has no parameters, set "parameters_examples" to {{}}.
- If the endpoint has no request body, set "request_body_examples" to {{}}.
"""


# Module-level prompt uses the configured default version.
# LLMEnrichmentAgent rebuilds it per-instance when a different spec version is detected.
SYSTEM_PROMPT = _build_system_prompt(Config.OPENAPI_VERSION)


class LLMAuthenticationError(Exception):
    """Raised when the LLM API returns a non-retriable authentication error."""


class LLMEnrichmentAgent:
    """
    Agent that uses an LLM to generate realistic, multiple examples per
    endpoint/retcode pair for OpenAPI endpoints.
    """

    def __init__(self, model: Optional[str] = None, openapi_version: Optional[str] = None) -> None:
        self.model = model or Config.LLM_MODEL
        self.client = OpenAI(
            api_key=Config.OPENROUTER_API_KEY,
            base_url=Config.OPENROUTER_API_BASE,
        )
        self.rate_limiter = RateLimiter(Config.RATE_LIMIT_REQUESTS_PER_MINUTE)
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        # Build the system prompt using the spec's actual version (may differ from
        # the global Config default, e.g. Swagger 2.0 specs on a 3.0 installation).
        effective_version = openapi_version or Config.OPENAPI_VERSION
        self._system_prompt = _build_system_prompt(effective_version)
        logger.info(
            "LLMEnrichmentAgent initialized with model: %s (base_url: %s, openapi_version: %s)",
            self.model,
            Config.OPENROUTER_API_BASE,
            effective_version,
        )

    def enrich_endpoint(self, endpoint: EndpointInfo, api_context: str) -> Dict[str, Any]:
        """
        Call the LLM to generate multiple examples for a single endpoint.
        Returns a dict with parameter, request body, and response body examples.
        Raises LLMAuthenticationError immediately on 401/403 — do not retry.
        """
        user_message = self._build_user_message(endpoint, api_context)
        logger.info(
            "Enriching endpoint: %s %s (response codes: %s)",
            endpoint.method,
            endpoint.path,
            endpoint.response_codes,
        )

        response_text = self._call_llm_with_retry(user_message)
        examples = self._parse_json_response(response_text, endpoint)
        return examples

    def _build_user_message(self, endpoint: EndpointInfo, api_context: str) -> str:
        """Build the user message for the LLM prompt."""
        params_info = json.dumps(endpoint.parameters, indent=2) if endpoint.parameters else "None"
        req_body_info = json.dumps(endpoint.request_body, indent=2) if endpoint.request_body else "None"
        responses_info = json.dumps(endpoint.responses, indent=2)

        # Classify response codes to guide the LLM
        success_codes = [c for c in endpoint.response_codes if str(c).startswith(("2",))]
        error_codes = [c for c in endpoint.response_codes
                       if str(c).startswith(("4", "5")) or str(c) == "default"]

        guidance = ""
        if error_codes:
            guidance = (
                f"\n\nFor error codes {error_codes}: generate at least 3 named examples each, "
                "using wrong data types, boundary violations, and null/missing values as described "
                "in the system instructions. These examples are intentionally invalid inputs."
            )
        if success_codes:
            guidance += (
                f"\n\nFor success codes {success_codes}: generate at least 2 named examples "
                "('typical' and 'edge_case') with realistic valid values."
            )

        return (
            f"API Context: {api_context}\n\n"
            f"Endpoint: {endpoint.method} {endpoint.path}\n"
            f"Operation ID: {endpoint.operation_id or 'N/A'}\n"
            f"Summary: {endpoint.summary or 'N/A'}\n"
            f"Description: {endpoint.description or 'N/A'}\n\n"
            f"Parameters:\n{params_info}\n\n"
            f"Request Body:\n{req_body_info}\n\n"
            f"Responses:\n{responses_info}\n\n"
            f"Response codes to cover: {endpoint.response_codes}"
            f"{guidance}\n\n"
            "Generate multiple named examples for ALL response codes listed above, "
            "following the exact JSON structure specified in the system instructions."
        )

    @retry(
        stop=stop_after_attempt(Config.RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=Config.BACKOFF_FACTOR,
            min=Config.RETRY_DELAY,
            max=120,
        ),
        # Do NOT retry on LLMAuthenticationError — it is a permanent failure.
        retry=retry_if_not_exception_type(LLMAuthenticationError),
        reraise=True,
    )
    def _call_llm_with_retry(self, user_message: str) -> str:
        """
        Call the LLM API with rate limiting and retry logic.

        Authentication errors (HTTP 401/403) are detected and re-raised as
        LLMAuthenticationError to bypass the retry decorator and fail fast.
        """
        self.rate_limiter.wait()

        logger.debug("Sending request to LLM...")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=Config.LLM_TEMPERATURE,
                seed=Config.LLM_SEED,
            )
        except (AuthenticationError, PermissionDeniedError) as exc:
            self._raise_auth_error(exc)
        except APIStatusError as exc:
            if exc.status_code in NON_RETRIABLE_STATUS_CODES:
                self._raise_auth_error(exc)
            logger.warning(
                "LLM API returned HTTP %d — will retry if attempts remain. Detail: %s",
                exc.status_code,
                exc.message,
            )
            raise

        usage = response.usage
        if usage:
            self.total_input_tokens += usage.prompt_tokens
            self.total_output_tokens += usage.completion_tokens
            logger.debug(
                "Token usage — input: %d, output: %d",
                usage.prompt_tokens,
                usage.completion_tokens,
            )

        content = response.choices[0].message.content or ""
        return content.strip()

    @staticmethod
    def _raise_auth_error(exc: Exception) -> None:
        """Log a clear diagnostic and raise LLMAuthenticationError."""
        logger.error(
            "Authentication failed when calling the LLM API.\n"
            "  Cause   : %s\n"
            "  Solution: Check that OPENROUTER_API_KEY in your .env file is set to a\n"
            "            valid OpenRouter API key. OPENROUTER_API_BASE must point to\n"
            "            https://openrouter.ai/api/v1\n"
            "            Obtain your key at: https://openrouter.ai/keys",
            exc,
        )
        raise LLMAuthenticationError(
            "LLM API authentication failed (HTTP 401/403). "
            "Verify OPENROUTER_API_KEY and OPENROUTER_API_BASE in your .env file."
        ) from exc

    def _parse_json_response(
        self, response_text: str, endpoint: EndpointInfo
    ) -> Dict[str, Any]:
        """
        Parse the LLM JSON response, stripping any accidental markdown fences.
        Normalises the parameters_examples and request_body_examples fields to
        always use the list-of-named-examples structure, even if the LLM returns
        the old single-dict format (for backward compatibility).
        Returns an empty structure on failure.
        """
        # Sanitize: remove markdown code fences if present
        cleaned = response_text
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            start = 1 if lines[0].startswith("```") else 0
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            cleaned = "\n".join(lines[start:end])

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error(
                "Failed to parse LLM JSON response for %s %s: %s",
                endpoint.method,
                endpoint.path,
                exc,
            )
            logger.debug("Raw LLM response: %s", response_text)
            return {
                "parameters_examples": {},
                "request_body_examples": {},
                "response_body_examples": {},
            }

        # Normalise parameters_examples: ensure each retcode maps to a list
        param_ex = data.get("parameters_examples", {})
        if isinstance(param_ex, dict):
            for code, value in param_ex.items():
                if isinstance(value, dict):
                    # Old format: single dict without _name — wrap in a list
                    if "_name" not in value:
                        param_ex[code] = [{"_name": "example_1", **value}]
                    else:
                        param_ex[code] = [value]
                elif not isinstance(value, list):
                    param_ex[code] = []
        data["parameters_examples"] = param_ex

        # Normalise request_body_examples: ensure each retcode maps to a list
        req_ex = data.get("request_body_examples", {})
        if isinstance(req_ex, dict):
            for code, value in req_ex.items():
                if isinstance(value, dict):
                    if "_name" not in value:
                        req_ex[code] = [{"_name": "example_1", "value": value}]
                    else:
                        req_ex[code] = [value]
                elif not isinstance(value, list):
                    req_ex[code] = []
        data["request_body_examples"] = req_ex

        logger.debug(
            "Successfully parsed LLM response for %s %s.",
            endpoint.method,
            endpoint.path,
        )
        return data

    def get_token_usage(self) -> Dict[str, int]:
        """Return accumulated token usage across all LLM calls."""
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
        }
