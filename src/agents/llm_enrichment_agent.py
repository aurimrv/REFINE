"""
LLMEnrichmentAgent
------------------
Responsible for calling the LLM (via OpenAI-compatible API) to generate
realistic examples for each endpoint and response code in the OpenAPI spec.
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
    retry_if_exception_type,
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

For EACH response code of the endpoint, you must generate:
1. Realistic example values for ALL parameters ({param_locations}).
2. A realistic example request body (if applicable).
3. A realistic example response body that matches the HTTP status code semantics.

OpenAPI {openapi_version} compatibility rules (STRICTLY FOLLOW):
{body_param_rule}
- Parameter 'in' field MUST be one of: {param_locations}.
- Response code keys MUST be strings (e.g. "200", "404"), never integers.
- Do NOT add fields that are not part of the OpenAPI {openapi_version} specification.
- Use realistic data (real country names, valid ISO codes, real currencies, etc.) — NOT placeholder values like "string" or "example".
- For error responses (4xx, 5xx), generate appropriate error messages.
- Return ONLY a valid JSON object. Do NOT include markdown code fences or any extra text.
- The JSON must follow this exact structure:

{{
  "parameters_examples": {{
    "<response_code>": {{
      "<param_name>": <example_value>
    }}
  }},
  "request_body_examples": {{
    "<response_code>": {{ ... }}
  }},
  "response_body_examples": {{
    "<response_code>": {{ ... }}
  }}
}}

If the endpoint has no parameters, set "parameters_examples" to {{}}.
If the endpoint has no request body, set "request_body_examples" to {{}}.
"""


# Build the system prompt once at module load time using the configured version
SYSTEM_PROMPT = _build_system_prompt(Config.OPENAPI_VERSION)


class LLMAuthenticationError(Exception):
    """Raised when the LLM API returns a non-retriable authentication error."""


class LLMEnrichmentAgent:
    """
    Agent that uses an LLM to generate realistic examples for OpenAPI endpoints.
    """

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or Config.LLM_MODEL
        self.client = OpenAI(
            api_key=Config.OPENROUTER_API_KEY,
            base_url=Config.OPENROUTER_API_BASE,
        )
        self.rate_limiter = RateLimiter(Config.RATE_LIMIT_REQUESTS_PER_MINUTE)
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        logger.info(
            "LLMEnrichmentAgent initialized with model: %s (base_url: %s)",
            self.model,
            Config.OPENROUTER_API_BASE,
        )

    def enrich_endpoint(self, endpoint: EndpointInfo, api_context: str) -> Dict[str, Any]:
        """
        Call the LLM to generate examples for a single endpoint.
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

        return (
            f"API Context: {api_context}\n\n"
            f"Endpoint: {endpoint.method} {endpoint.path}\n"
            f"Operation ID: {endpoint.operation_id or 'N/A'}\n"
            f"Summary: {endpoint.summary or 'N/A'}\n"
            f"Description: {endpoint.description or 'N/A'}\n\n"
            f"Parameters:\n{params_info}\n\n"
            f"Request Body:\n{req_body_info}\n\n"
            f"Responses:\n{responses_info}\n\n"
            f"Response codes to cover: {endpoint.response_codes}\n\n"
            "Generate realistic examples for ALL response codes listed above."
        )

    @retry(
        stop=stop_after_attempt(Config.RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=Config.BACKOFF_FACTOR,
            min=Config.RETRY_DELAY,
            max=120,
        ),
        # Do NOT retry on LLMAuthenticationError — it is a permanent failure.
        # Retry only on transient errors (network issues, 429, 5xx, etc.).
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
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=Config.LLM_TEMPERATURE,
                seed=Config.LLM_SEED,
            )
        except (AuthenticationError, PermissionDeniedError) as exc:
            # These are permanent failures — no point in retrying.
            self._raise_auth_error(exc)
        except APIStatusError as exc:
            if exc.status_code in NON_RETRIABLE_STATUS_CODES:
                self._raise_auth_error(exc)
            # For other HTTP errors (429, 5xx), let tenacity retry.
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
            logger.debug(
                "Successfully parsed LLM response for %s %s.",
                endpoint.method,
                endpoint.path,
            )
            return data
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

    def get_token_usage(self) -> Dict[str, int]:
        """Return accumulated token usage across all LLM calls."""
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
        }
