"""
SourceAnalyzerAgent
-------------------
Responsible for scanning a source code directory, collecting relevant source
files, and using an LLM to extract all implemented API endpoints and their
HTTP response codes.

The agent is language-agnostic: it reads source files as plain text and relies
on the LLM to understand any framework or language (JAX-RS, Spring, Flask,
FastAPI, Express, etc.).

Output is a list of ImplementedEndpoint objects that can be compared against
the OpenAPI specification by the DiscrepancyReporterAgent.

False-positive prevention strategy:
  - Only backend source files are analyzed (server-side code that DEFINES routes).
  - Frontend/client-side files (JS, TS, HTML, CSS, minified bundles) are excluded.
  - Static resource files (openapi.yaml, swagger.json, etc.) are excluded.
  - The LLM is explicitly instructed to extract only route DEFINITIONS, not
    client-side HTTP calls or URL strings found in documentation/config files.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from openai import OpenAI, AuthenticationError, PermissionDeniedError, APIStatusError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_not_exception_type

from src.agents.llm_enrichment_agent import LLMAuthenticationError
from src.utils.config import Config
from src.utils.logger import setup_logger
from src.utils.rate_limiter import RateLimiter

logger = setup_logger("source_analyzer_agent")

# ---------------------------------------------------------------------------
# Backend-only source file extensions.
# JavaScript and TypeScript are intentionally EXCLUDED because they are almost
# always frontend/client code in typical web projects. If the project is a
# Node.js/Express backend, the user should place the backend source in a
# dedicated directory and point --api-src to it.
# ---------------------------------------------------------------------------
BACKEND_EXTENSIONS = {
    # JVM
    ".java", ".kt", ".groovy", ".scala",
    # Python
    ".py",
    # Go
    ".go",
    # Ruby
    ".rb",
    # PHP
    ".php",
    # C# / .NET
    ".cs",
    # Rust
    ".rs",
    # C / C++
    ".c", ".cpp", ".h", ".hpp",
}

# YAML/XML config files that may declare routes (e.g., Spring routes, web.xml)
# but NOT OpenAPI/Swagger spec files.
CONFIG_EXTENSIONS = {".xml"}

# Directories that are never relevant for API endpoint analysis.
# These names must match an ENTIRE path segment (not a substring) to avoid
# discarding legitimate implementation files whose paths happen to contain
# words like "test" (e.g. Maven's src/test/ layout).
EXCLUDED_DIRS = {
    ".git", ".svn", "node_modules", "__pycache__", ".idea", ".vscode",
    "target", "build", "dist", "out", ".gradle", ".mvn",
    "static", "webapp", "public", "assets",
}

# Path-segment suffixes that mark a directory tree as test-only.
# A file is excluded when ANY of its ancestor directory names matches one of
# these values exactly (case-insensitive).  Using a separate set keeps the
# logic explicit and easy to extend.
TEST_DIRS = {"test", "tests", "spec", "specs", "it", "integrationtest", "integrationtests"}

# File name patterns that indicate static/generated/documentation files to skip
EXCLUDED_FILENAME_PATTERNS = {
    "openapi", "swagger", "api-docs",          # OpenAPI/Swagger spec files
    "bootstrap", "jquery", "angular", "react",  # Frontend libraries
    ".min.",                                     # Minified files
}

# Maximum characters per source file chunk sent to the LLM
MAX_CHUNK_CHARS = 12_000

SYSTEM_PROMPT = """You are an expert software engineer specializing in REST API analysis.
Your task is to analyze BACKEND server-side source code files and extract REST API endpoints
that are DEFINED and IMPLEMENTED in the code — not called or referenced.

CRITICAL RULES — read carefully before extracting:
1. Extract ONLY route/endpoint DEFINITIONS: annotations like @GET, @Path, @RequestMapping,
   @app.route(), router.get(), etc. that define server-side handlers.
2. DO NOT extract endpoints from:
   - Client-side HTTP calls (fetch, axios, XMLHttpRequest, $.ajax, RestTemplate, etc.)
   - URL strings in comments, documentation, or configuration values
   - OpenAPI/Swagger YAML or JSON specification files
   - Test files or mock servers
   - Frontend JavaScript code
3. For each endpoint, identify:
   a. The HTTP method (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS).
   b. The full URL path pattern assembled from all path annotations/prefixes
      (e.g., if a class has @Path("/v2") and a method has @Path("/alpha/{code}"),
      the full path is /v2/alpha/{code}).
   c. All HTTP response/status codes that the implementation explicitly returns or throws.
   d. A brief description of what the endpoint does.
   e. The parameters (path, query, header) the endpoint accepts.
4. Return ONLY a valid JSON array. Do NOT include markdown fences or extra text.
5. If no endpoint DEFINITIONS are found, return an empty JSON array: []

Each element must follow this exact structure:
{
  "method": "GET",
  "path": "/v2/alpha/{alphacode}",
  "response_codes": ["200", "400", "404"],
  "description": "Returns a country by its ISO alpha code.",
  "parameters": [
    {"name": "alphacode", "in": "path", "description": "ISO 3166-1 alpha-2 or alpha-3 code"}
  ]
}
"""


@dataclass
class ImplementedEndpoint:
    """Represents a single REST endpoint found in the source code."""
    method: str
    path: str
    response_codes: List[str]
    description: str = ""
    parameters: List[dict] = field(default_factory=list)
    source_file: str = ""


class SourceAnalyzerAgent:
    """
    Agent that scans a source directory and uses an LLM to extract all
    implemented REST API endpoints and their response codes.
    """

    def __init__(self, src_home: Path, model: Optional[str] = None) -> None:
        self.src_home = src_home.resolve()
        self.model = model or Config.LLM_MODEL
        self.client = OpenAI(
            api_key=Config.OPENROUTER_API_KEY,
            base_url=Config.OPENROUTER_API_BASE,
        )
        self.rate_limiter = RateLimiter(Config.RATE_LIMIT_REQUESTS_PER_MINUTE)
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        logger.info(
            "SourceAnalyzerAgent initialized. src_home=%s, model=%s",
            self.src_home,
            self.model,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self) -> List[ImplementedEndpoint]:
        """
        Scan the source directory, send relevant backend files to the LLM
        in chunks, and return a deduplicated list of ImplementedEndpoint objects.
        """
        source_files = self._collect_source_files()
        if not source_files:
            logger.warning("No relevant backend source files found under: %s", self.src_home)
            return []

        logger.info(
            "Found %d relevant source file(s) to analyze under %s.",
            len(source_files),
            self.src_home,
        )

        all_endpoints: List[ImplementedEndpoint] = []
        chunks = self._build_chunks(source_files)
        logger.info("Source code split into %d chunk(s) for LLM analysis.", len(chunks))

        for idx, (chunk_text, chunk_files) in enumerate(chunks, start=1):
            logger.info(
                "[%d/%d] Analyzing chunk covering %d file(s): %s",
                idx,
                len(chunks),
                len(chunk_files),
                ", ".join(chunk_files),
            )
            endpoints = self._analyze_chunk(chunk_text, chunk_files)
            all_endpoints.extend(endpoints)

        deduplicated = self._deduplicate(all_endpoints)
        logger.info(
            "Source analysis complete. Found %d unique implemented endpoint(s).",
            len(deduplicated),
        )
        return deduplicated

    def get_token_usage(self) -> dict:
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _collect_source_files(self) -> List[Path]:
        """
        Recursively collect backend source files, skipping:
        - Excluded directories (frontend, build artifacts, test code)
        - Non-backend file types (JS, TS, HTML, CSS, YAML, etc.)
        - Files whose names suggest they are specs, libs, or minified bundles
        """
        collected: List[Path] = []
        for path in sorted(self.src_home.rglob("*")):
            if not path.is_file():
                continue

            # Build the set of individual directory-name segments for this file,
            # relative to src_home, so we match on whole names only (not substrings).
            rel_parts = path.relative_to(self.src_home).parts  # e.g. ('src','main','java','...')
            rel_parts_lower = {p.lower() for p in rel_parts[:-1]}  # exclude the filename itself

            # Skip build/tooling/frontend directories (exact segment match)
            if any(excl in rel_parts_lower for excl in EXCLUDED_DIRS):
                logger.debug("Skipping (excluded dir): %s", path.relative_to(self.src_home))
                continue

            # Skip dedicated test trees only when the test directory sits directly
            # under src_home OR directly under a standard source layout root
            # (e.g. Maven's src/test/, Gradle's test/).
            # Strategy: a segment is treated as a test root only when it appears
            # as the first or second element of the relative path, which covers:
            #   test/...                  (Gradle single-project)
            #   src/test/...              (Maven standard)
            #   src/integrationTest/...   (Spring Boot integration tests)
            # Files deeper in the tree (e.g. src/main/java/myapp/TestHelper.java)
            # are NOT excluded — the word "test" appears in the filename, not in a
            # leading directory segment.
            leading_parts_lower = [p.lower() for p in rel_parts[:-1]]
            is_test_tree = any(
                seg in TEST_DIRS
                for seg in leading_parts_lower[:3]   # check first 3 directory levels
            )
            if is_test_tree:
                logger.debug("Skipping (test tree): %s", path.relative_to(self.src_home))
                continue

            # Also skip paths that contain "webapp" or "static" anywhere
            path_str_lower = str(path).lower()
            if "/webapp/" in path_str_lower or "/static/" in path_str_lower:
                continue

            ext = path.suffix.lower()
            name_lower = path.name.lower()

            # Skip files with excluded name patterns (openapi, swagger, minified, etc.)
            if any(pattern in name_lower for pattern in EXCLUDED_FILENAME_PATTERNS):
                logger.debug("Skipping non-backend file: %s", path.relative_to(self.src_home))
                continue

            # Accept backend source files
            if ext in BACKEND_EXTENSIONS:
                collected.append(path)
                continue

            # Accept XML config files (web.xml, routes.xml, etc.) but not specs
            if ext in CONFIG_EXTENSIONS:
                collected.append(path)

        return collected

    def _build_chunks(self, files: List[Path]) -> List[tuple]:
        """
        Group source files into chunks that fit within MAX_CHUNK_CHARS.
        Returns list of (chunk_text, [relative_file_names]).
        """
        chunks = []
        current_text = ""
        current_files = []

        for fpath in files:
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                logger.warning("Could not read %s: %s — skipping.", fpath, exc)
                continue

            rel_name = str(fpath.relative_to(self.src_home))
            file_block = f"\n\n// === FILE: {rel_name} ===\n{content}"

            if current_text and len(current_text) + len(file_block) > MAX_CHUNK_CHARS:
                chunks.append((current_text, list(current_files)))
                current_text = file_block
                current_files = [rel_name]
            else:
                current_text += file_block
                current_files.append(rel_name)

        if current_text:
            chunks.append((current_text, list(current_files)))

        return chunks

    def _analyze_chunk(self, chunk_text: str, chunk_files: List[str]) -> List[ImplementedEndpoint]:
        """Send a chunk of source code to the LLM and parse the returned endpoints."""
        user_message = (
            f"Analyze the following BACKEND source code files and extract only the REST API "
            f"endpoint DEFINITIONS (server-side route handlers, not client calls).\n"
            f"Files included in this chunk: {', '.join(chunk_files)}\n\n"
            f"{chunk_text}"
        )
        response_text = self._call_llm(user_message)
        return self._parse_response(response_text, chunk_files)

    @retry(
        stop=stop_after_attempt(Config.RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=Config.BACKOFF_FACTOR,
            min=Config.RETRY_DELAY,
            max=120,
        ),
        retry=retry_if_not_exception_type(LLMAuthenticationError),
        reraise=True,
    )
    def _call_llm(self, user_message: str) -> str:
        """Call the LLM with retry logic. Fails fast on 401/403."""
        self.rate_limiter.wait()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                # Source-code analysis is deterministic fact-extraction: always
                # use temperature=0 regardless of the global Config setting so
                # that repeated runs on the same codebase produce identical output.
                temperature=0.0,
                seed=Config.LLM_SEED,
            )
        except (AuthenticationError, PermissionDeniedError) as exc:
            self._raise_auth_error(exc)
        except APIStatusError as exc:
            if exc.status_code in {401, 403}:
                self._raise_auth_error(exc)
            logger.warning("LLM API HTTP %d — will retry. Detail: %s", exc.status_code, exc.message)
            raise

        usage = response.usage
        if usage:
            self.total_input_tokens += usage.prompt_tokens
            self.total_output_tokens += usage.completion_tokens

        return (response.choices[0].message.content or "").strip()

    def _parse_response(self, response_text: str, chunk_files: List[str]) -> List[ImplementedEndpoint]:
        """Parse the LLM JSON array response into ImplementedEndpoint objects."""
        cleaned = response_text
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            start = 1 if lines[0].startswith("```") else 0
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            cleaned = "\n".join(lines[start:end])

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse LLM response for chunk %s: %s", chunk_files, exc)
            logger.debug("Raw response: %s", response_text)
            return []

        if not isinstance(data, list):
            logger.error("Expected JSON array from LLM, got: %s", type(data).__name__)
            return []

        endpoints = []
        for item in data:
            try:
                path = item.get("path", "")
                # Skip any path that looks like a full URL (http/https) —
                # these are client-side calls that slipped through
                if path.startswith("http://") or path.startswith("https://"):
                    logger.debug("Skipping client-side URL found in source: %s", path)
                    continue
                ep = ImplementedEndpoint(
                    method=item.get("method", "GET").upper(),
                    path=path,
                    response_codes=[str(c) for c in item.get("response_codes", [])],
                    description=item.get("description", ""),
                    parameters=item.get("parameters", []),
                    source_file=", ".join(chunk_files),
                )
                endpoints.append(ep)
            except Exception as exc:
                logger.warning("Skipping malformed endpoint entry: %s — %s", item, exc)

        return endpoints

    @staticmethod
    def _deduplicate(endpoints: List[ImplementedEndpoint]) -> List[ImplementedEndpoint]:
        """Remove duplicate endpoints (same method + path), merging response codes.

        Normalises the path to lowercase with trailing slash stripped before
        building the deduplication key, so two entries that differ only in
        capitalisation or a trailing slash are correctly collapsed into one.
        The first occurrence wins for all non-code fields; response codes from
        all duplicates are merged.
        """
        seen: dict = {}
        for ep in endpoints:
            key = (ep.method.upper(), ep.path.rstrip("/").lower())
            if key not in seen:
                seen[key] = ep
            else:
                # Merge response codes from duplicate entries
                existing_codes = set(seen[key].response_codes)
                for code in ep.response_codes:
                    if code not in existing_codes:
                        seen[key].response_codes.append(code)
                        existing_codes.add(code)
        return list(seen.values())

    @staticmethod
    def _raise_auth_error(exc: Exception) -> None:
        logger.error(
            "Authentication failed when calling the LLM API.\n"
            "  Cause   : %s\n"
            "  Solution: Check that OPENROUTER_API_KEY in your .env file is set to a\n"
            "            valid OpenRouter API key.\n"
            "            Obtain your key at: https://openrouter.ai/keys",
            exc,
        )
        raise LLMAuthenticationError(
            "LLM API authentication failed (HTTP 401/403). "
            "Verify OPENROUTER_API_KEY and OPENROUTER_API_BASE in your .env file."
        ) from exc
