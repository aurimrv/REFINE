# OpenAPI Spec Improver

A multi-agent Python tool that enriches OpenAPI specifications with realistic
examples using an LLM, and optionally analyzes source code to detect
discrepancies between the specification and the implementation.

> **The described API does NOT need to be running or reachable.**
> All processing is performed through static analysis of the spec file and
> source code, combined with LLM inference. No HTTP calls are made to the
> API servers declared in the specification.

---

## Features

- **Spec-only enrichment** — Reads an OpenAPI spec (JSON or YAML) and adds
  realistic `example` values to every endpoint and response code via LLM.
- **Source code analysis** (`--api-src`) — Scans the implementation source
  code (any language/framework) and uses the LLM to extract all implemented
  endpoints and response codes.
- **Discrepancy report** — When `--api-src` is provided, compares spec vs
  implementation and generates a detailed Markdown report highlighting:
  - Endpoints declared in the spec but missing in the implementation
  - Endpoints implemented but absent from the spec
  - Response code mismatches
  - Parameter mismatches
- **Implementation-aligned enrichment** — When `--api-src` is provided, the
  enriched spec is 100% aligned with the actual implementation (endpoints and
  response codes found only in the source code are added to the output spec).
- **Token usage logging** — All LLM token consumption is logged to a CSV file.

---

## Architecture

```
main.py (CLI)
    └── OrchestratorAgent
            ├── SpecParserAgent           — loads and parses the OpenAPI spec
            ├── SourceAnalyzerAgent       — extracts endpoints from source code (--api-src only)
            ├── DiscrepancyReporterAgent  — compares spec vs impl, writes Markdown report
            ├── LLMEnrichmentAgent        — calls LLM to generate realistic examples
            └── SpecWriterAgent           — merges examples and writes the enriched spec
```

---

## Installation

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set your OPENROUTER_API_KEY
```

---

## Usage

```bash
# Spec-only enrichment (no source code required)
python main.py --api-spec restcountries.json

# Enrichment + source code analysis + discrepancy report
python main.py --api-spec restcountries.json --api-src ./restcountries/

# Specify LLM model explicitly
python main.py --api-spec restcountries.json --llm-model openai/gpt-4o

# Using absolute paths
python main.py --api-spec /path/to/api-spec.json --api-src /path/to/src/
```

### Output files

| Mode | Output |
|---|---|
| Spec-only | `<spec_name>_<timestamp>.json` — enriched spec |
| Spec + Source | `<spec_name>_<timestamp>.json` — enriched spec aligned with implementation |
| Spec + Source | `<spec_name>_discrepancy_<timestamp>.md` — discrepancy report |

Both output files are saved in the same directory as the original spec file.

---

## Configuration (`.env`)

Key settings in `.env`:

| Variable | Description | Default |
|---|---|---|
| `OPENROUTER_API_KEY` | Your OpenRouter API key (get one at [openrouter.ai/keys](https://openrouter.ai/keys)) | *(required)* |
| `OPENROUTER_API_BASE` | OpenRouter API base URL | `https://openrouter.ai/api/v1` |
| `LLM_MODEL` | LLM model identifier | `openai/gpt-4o-mini` |
| `LLM_TEMPERATURE` | Sampling temperature | `0.7` |
| `LLM_SEED` | Reproducibility seed | `42` |
| `LOG_LEVEL` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | Max LLM requests per minute | `60` |
| `RETRY_ATTEMPTS` | Number of retry attempts on transient errors | `3` |
| `RETRY_DELAY` | Initial retry delay in seconds | `2.0` |
| `BACKOFF_FACTOR` | Exponential backoff multiplier | `3.0` |

---

## Project Structure

```
openapi-improver/
├── main.py                          # CLI entry point
├── requirements.txt
├── .env.example
├── src/
│   ├── agents/
│   │   ├── orchestrator_agent.py    # Pipeline coordinator
│   │   ├── spec_parser_agent.py     # OpenAPI spec parser
│   │   ├── source_analyzer_agent.py # Source code endpoint extractor
│   │   ├── discrepancy_reporter_agent.py  # Spec vs impl comparator
│   │   ├── llm_enrichment_agent.py  # LLM-based example generator
│   │   └── spec_writer_agent.py     # Enriched spec writer
│   ├── models/
│   │   └── openapi_models.py        # Pydantic data models
│   └── utils/
│       ├── config.py                # Environment configuration
│       ├── logger.py                # Logging setup
│       └── rate_limiter.py          # API rate limiter
```
