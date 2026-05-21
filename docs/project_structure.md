# REFINE — Project Structure

This document describes the layout of the REFINE codebase and the responsibility
of every component. REFINE (REst From code and INferred Enhancement) is an
LLM-based multi-agent tool that aligns an OpenAPI specification with the API
source code and enriches it with realistic examples. All processing is static:
the tool never calls the API it documents.

---

## Directory tree

```
REFINE/
├── main.py                              # CLI entry point
├── requirements.txt                     # Core Python dependencies
├── .env.example                         # Configuration template (copy to .env)
├── .gitignore
├── README.md            
│
├── docs/
│   └── refine-architecture.pdf          # Rendered architecture diagram
|   └── project_structure.md
│
├── schemas/                             # Official OpenAPI JSON Schemas
│   ├── openapi-2.0-schema.json          #   Swagger 2.0
│   ├── openapi-3.0.0-schema.json        #   OpenAPI 3.0.0
│   └── openapi-3.1.0-schema.json        #   OpenAPI 3.1.0
│
└── src/
    ├── __init__.py
    │
    ├── agents/                          # Orchestrator + six task agents
    │   ├── __init__.py
    │   ├── orchestrator_agent.py        # Pipeline coordinator
    │   ├── spec_parser_agent.py         # Loads/parses the OpenAPI spec
    │   ├── source_analyzer_agent.py     # Extracts endpoints from source code
    │   ├── discrepancy_reporter_agent.py# Compares spec vs. implementation
    │   ├── llm_enrichment_agent.py      # Generates examples via the LLM
    │   ├── spec_validator_agent.py      # Validates + auto-repairs the spec
    │   └── spec_writer_agent.py         # Merges examples, writes the spec
    │
    ├── models/                          # Pydantic data models
    │   ├── __init__.py
    │   └── openapi_models.py            # EndpointInfo and related models
    │
    └── utils/                           # Cross-cutting utilities
        ├── __init__.py
        ├── config.py                    # Environment/.env configuration
        ├── logger.py                    # Colored console + file logging
        └── rate_limiter.py              # Requests-per-minute rate limiter
```

---

## Entry point

### `main.py`
Command-line interface. Parses `--api-spec` (required), `--api-src` (optional),
and `--llm-model` (optional); loads the `.env` file; validates configuration
(API-key presence); resolves and checks the input paths; then constructs and
runs an `OrchestratorAgent`. Authentication failures are caught and reported
with an actionable message; any other failure exits with a non-zero status.

---

## Agents (`src/agents/`)

### `orchestrator_agent.py` — `OrchestratorAgent`
The coordinator. Runs the full pipeline and returns
`(enriched_spec_path, discrepancy_report_path)` — the second value is `None` in
spec-only mode. Responsibilities:

- Generates a single run timestamp shared by all output files.
- **Step 1** — parses the spec via `SpecParserAgent`, building the endpoint list
  and the API context string (title, version, description).
- **Step 2 (Mode B)** — runs `SourceAnalyzerAgent` to extract implemented
  endpoints.
- **Step 3 (Mode B)** — runs `DiscrepancyReporterAgent`, writes the Markdown
  report, then performs **status-code reconciliation**:
  - *Case A* — when the spec uses the catch-all `default`, replaces it with the
    concrete codes the implementation returns.
  - *Case B* — when the spec has explicit codes that differ from the
    implementation, replaces them with the implementation's codes.
  - Impl-only endpoints (`MISSING_IN_SPEC`) are converted to `EndpointInfo`,
    marked `_impl_only`, and queued for enrichment and insertion. Implementation
    paths are normalized against the spec base path so prefixes such as `/rest`
    align correctly.
- **Step 4** — enriches every endpoint via `LLMEnrichmentAgent`, using the
  version detected in the document.
- **Step 5** — merges examples and writes the enriched spec via
  `SpecWriterAgent`.
- **Step 6** — validates and auto-repairs via `SpecValidatorAgent`; if repairs
  were applied, the output file is rewritten.
- **Step 7** — aggregates token usage from all agents and appends a row to the
  per-run `token_usage_<timestamp>.csv` file.

### `spec_parser_agent.py` — `SpecParserAgent`
Loads the OpenAPI document from disk (read as JSON) and extracts one
`EndpointInfo` per `(path, method)` pair, merging path-level and operation-level
parameters. Detects the declared version (`openapi`/`swagger`) and derives the
**base-path prefix** (Swagger 2.0 `basePath`, or the path component of the first
OAS 3.x `servers[0].url`), exposed as `spec_base_path` for later path alignment.

### `source_analyzer_agent.py` — `SourceAnalyzerAgent`
Scans the `--api-src` directory and uses the LLM to extract implemented
endpoints. Key behavior:

- **File selection** — keeps only backend source files (by extension: Java,
  Kotlin, Python, Go, Ruby, PHP, C#, Rust, C/C++, plus XML config) and excludes
  build/tooling/frontend directories and dedicated test trees by whole-segment
  path matching. Spec, library, and minified files are skipped by name pattern.
- **Chunking** — concatenates files into chunks of up to `MAX_CHUNK_CHARS`
  (12,000) characters for LLM analysis.
- **Extraction prompt** — instructs the model to extract route *definitions*
  only (not client calls or documentation URLs) and to infer implicit status
  codes (e.g. include `500` for uncaught exceptions, `404`/`409` only when an
  explicit handler or exception mapper exists). Uses `temperature=0` for
  deterministic, repeatable extraction.
- **Output** — a deduplicated list of `ImplementedEndpoint` objects (duplicates
  merged by `method` + normalized `path`, response codes unioned).
- Tracks token usage and fails fast on 401/403.

### `discrepancy_reporter_agent.py` — `DiscrepancyReporterAgent`
Compares parsed spec endpoints against implemented endpoints and produces a
`DiscrepancyReport`. Each `(method, path)` pair is classified as `MATCH`,
`MISSING_IN_IMPL`, `MISSING_IN_SPEC`, `RETCODE_MISMATCH`, or `PARAM_MISMATCH`.
Implementation paths are stripped of the spec base-path prefix before
comparison. `write_report()` renders the findings as a Markdown document with an
executive-summary table and one section per category.

### `llm_enrichment_agent.py` — `LLMEnrichmentAgent`
Calls the LLM (OpenAI-compatible client against OpenRouter) to generate
**multiple named examples** per endpoint and response code:

- 2xx codes → at least `typical` and `edge_case`.
- 4xx/5xx codes → at least `invalid_type`, `boundary_violation`,
  `null_or_missing`.

The system prompt is **version-aware** (OAS 3.x emits `requestBody`; Swagger 2.0
uses body examples via extensions). Calls use retry with exponential backoff and
raise `LLMAuthenticationError` immediately on 401/403. The response parser is
robust to truncated/malformed JSON, applying four recovery strategies
(fence stripping, truncation at the last balanced brace, optional `json_repair`,
and structural salvage of complete sub-blocks) and normalizing legacy formats.

### `spec_validator_agent.py` — `SpecValidatorAgent`
Validates the enriched spec against the official JSON Schema for the detected
version (using `jsonschema`'s `Draft4Validator`) and applies a catalog of ten
version-aware auto-repair rules (R1–R10) before re-validating. Remaining errors
are logged as warnings. If `jsonschema` is not installed, validation is skipped
gracefully. See the README for the full rule table.

### `spec_writer_agent.py` — `SpecWriterAgent`
Deep-copies the original spec and merges the enrichment payloads. Version-aware:

- Inserts impl-only endpoints as minimal-but-valid operations.
- Expands `default` into explicit response entries (Case A) and reconciles
  explicit codes (Case B).
- Filters out any LLM-invented response codes that do not exist in the
  operation, preventing phantom examples from leaking into the output.
- Writes parameter examples (scalar `example` plus the `x-parameter-examples`
  extension), request-body examples, and response-body examples in the correct
  location for the spec version.
- Persists the result as `<spec_name>_<timestamp>.json` next to the original.

---

## Models (`src/models/`)

### `openapi_models.py`
Pydantic models supporting the pipeline:

- **`EndpointInfo`** — the central record passed between agents: path, method,
  operation id, summary, description, parameters, request body, response codes,
  and the raw responses dict. (Two sibling models, `ParameterModel`,
  `ResponseModel`, and `OperationModel`, mirror OpenAPI sub-objects.)

Two additional dataclasses live next to the agents that own them:
`ImplementedEndpoint` (in `source_analyzer_agent.py`) and
`EndpointDiscrepancy` / `DiscrepancyReport` (in `discrepancy_reporter_agent.py`).

---

## Utilities (`src/utils/`)

### `config.py` — `Config`
Central configuration loaded from environment variables / `.env`. Exposes all
OpenRouter, LLM, logging, rate-limit, retry, and OpenAPI-version settings;
resolves schema-file paths (`get_schema_path`); detects the spec version
(`detect_spec_version`); and validates required configuration (`validate`),
including detection of placeholder API keys.

### `logger.py` — `setup_logger`
Returns a logger with colored console output and a daily file handler under
`logs/`. Guards against duplicate handlers and honors `LOG_LEVEL`.

### `rate_limiter.py` — `RateLimiter`
Thread-safe requests-per-minute limiter. `wait()` blocks just long enough to
respect the configured minimum interval between LLM calls.

---

## Supporting files

- **`schemas/`** — the three bundled OpenAPI JSON Schemas selected by detected
  version for validation.
- **`docs/refine-architecture.pdf`** — the rendered architecture diagram.
- **`.env.example`** — template listing every configurable variable; copy to
  `.env` and set `OPENROUTER_API_KEY`.
- **`requirements.txt`** — core dependencies (`openai`, `python-dotenv`,
  `pydantic`, `colorlog`, `tenacity`). `jsonschema` (validation) and
  `json_repair` (optional JSON recovery) are additional dependencies.

---

## Data flow summary

```
spec file ──▶ SpecParserAgent ──▶ EndpointInfo[]
                                       │
source dir ─▶ SourceAnalyzerAgent ─▶ ImplementedEndpoint[]   (Mode B)
                                       │
              DiscrepancyReporterAgent ┤──▶ discrepancy_<ts>.md   (Mode B)
                                       │    + status-code reconciliation
                                       ▼
              LLMEnrichmentAgent  ──▶ examples per endpoint
                                       ▼
              SpecWriterAgent     ──▶ <spec>_<ts>.json (enriched)
                                       ▼
              SpecValidatorAgent  ──▶ validated + auto-repaired spec
                                       ▼
              OrchestratorAgent   ──▶ token_usage_<ts>.csv
```
