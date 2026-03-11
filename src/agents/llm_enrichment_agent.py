"""
LLMEnrichmentAgent
------------------
Responsible for calling the LLM (via OpenAI-compatible API) to generate
realistic examples for each endpoint and response code in the OpenAPI spec.
Uses retry logic and rate limiting to handle API constraints gracefully.
"""

import json
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.models.openapi_models import EndpointInfo
from src.utils.config import Config
from src.utils.logger import setup_logger
from src.utils.rate_limiter import RateLimiter

logger = setup_logger("llm_enrichment_agent")

SYSTEM_PROMPT = """You are an expert API documentation engineer specializing in OpenAPI Specification 3.x.
Your task is to enrich an OpenAPI endpoint definition by adding realistic, clear, and meaningful examples.

For EACH response code of the endpoint, you must generate:
1. Realistic example values for ALL parameters (path, query, header, cookie).
2. A realistic example request body (if applicable).
3. A realistic example response body that matches the HTTP status code semantics.

Rules:
- Use realistic data (real country names, valid ISO codes, real currencies, etc.) — NOT placeholder values like "string" or "example".
- For error responses (4xx, 5xx), generate appropriate error messages.
- Return ONLY a valid JSON object. Do NOT include markdown code fences or any extra text.
- The JSON must follow this exact structure:

{
  "parameters_examples": {
    "<response_code>": {
      "<param_name>": <example_value>
    }
  },
  "request_body_examples": {
    "<response_code>": { ... }
  },
  "response_body_examples": {
    "<response_code>": { ... }
  }
}

If the endpoint has no parameters, set "parameters_examples" to {}.
If the endpoint has no request body, set "request_body_examples" to {}.
"""


class LLMEnrichmentAgent:
    """
    Agent that uses an LLM to generate realistic examples for OpenAPI endpoints.
    """

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or Config.LLM_MODEL
        self.client = OpenAI(
            api_key=Config.OPENAI_API_KEY,
            base_url=Config.OPENAI_API_BASE,
        )
        self.rate_limiter = RateLimiter(Config.RATE_LIMIT_REQUESTS_PER_MINUTE)
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        logger.info(
            "LLMEnrichmentAgent initialized with model: %s (base_url: %s)",
            self.model,
            Config.OPENAI_API_BASE,
        )

    def enrich_endpoint(self, endpoint: EndpointInfo, api_context: str) -> Dict[str, Any]:
        """
        Call the LLM to generate examples for a single endpoint.
        Returns a dict with parameter, request body, and response body examples.
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
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _call_llm_with_retry(self, user_message: str) -> str:
        """Call the LLM API with rate limiting and retry logic."""
        self.rate_limiter.wait()

        logger.debug("Sending request to LLM...")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=Config.LLM_TEMPERATURE,
            seed=Config.LLM_SEED,
        )

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
            # Remove first and last fence lines
            start = 1 if lines[0].startswith("```") else 0
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            cleaned = "\n".join(lines[start:end])

        try:
            data = json.loads(cleaned)
            logger.debug("Successfully parsed LLM response for %s %s.", endpoint.method, endpoint.path)
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
