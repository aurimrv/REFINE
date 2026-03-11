# OpenAPI Spec Improver

A multi-agent Python system that analyzes an OpenAPI specification file and generates an enriched version with **realistic examples** for every endpoint and response code, facilitating the creation of test cases.

---

## Architecture

The system follows a **multi-agent pipeline** pattern:

```
main.py (CLI)
    └── OrchestratorAgent
            ├── SpecParserAgent      — loads & parses the OpenAPI spec
            ├── LLMEnrichmentAgent   — calls the LLM to generate examples
            └── SpecWriterAgent      — merges examples & writes output file
```

### Project Structure

```
openapi-improver/
├── main.py                        # CLI entry point
├── requirements.txt
├── .env.example
├── README.md
├── logs/                          # Auto-created log files
└── src/
    ├── agents/
    │   ├── orchestrator_agent.py  # Pipeline coordinator
    │   ├── spec_parser_agent.py   # OpenAPI spec parser
    │   ├── llm_enrichment_agent.py# LLM-based example generator
    │   └── spec_writer_agent.py   # Enriched spec writer
    ├── models/
    │   └── openapi_models.py      # Pydantic data models
    └── utils/
        ├── config.py              # Centralized configuration
        ├── logger.py              # Structured logging setup
        └── rate_limiter.py        # API rate limiting
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure the environment

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Key settings in `.env`:

| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | Your OpenRouter (or OpenAI) API key | *(required)* |
| `OPENAI_API_BASE` | API base URL | `https://openrouter.ai/api/v1` |
| `LLM_MODEL` | LLM model identifier | `openai/gpt-4o-mini` |
| `LLM_TEMPERATURE` | Sampling temperature | `0.7` |
| `LLM_SEED` | Reproducibility seed | `42` |
| `LOG_LEVEL` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `RETRY_ATTEMPTS` | Number of retry attempts on API failure | `3` |
| `RETRY_DELAY` | Initial retry delay in seconds | `2.0` |
| `BACKOFF_FACTOR` | Exponential backoff multiplier | `3.0` |

---

## Usage

```bash
python main.py --api-spec <API_SPEC> [--llm-model <LLM_MODEL>]
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `--api-spec` | Yes | Path to the OpenAPI JSON file (relative or absolute) |
| `--llm-model` | No | LLM model to use (overrides `LLM_MODEL` in `.env`) |

### Examples

```bash
# Using a relative path
python main.py --api-spec restcountries.json

# Using an absolute path
python main.py --api-spec /data/specs/my-api.json

# Overriding the LLM model
python main.py --api-spec restcountries.json --llm-model openai/gpt-4o
```

---

## Output

The enriched specification is saved in the **same directory** as the input file, with a timestamp suffix:

```
restcountries_2026-03-02_11-03-00.json
```

Token usage is recorded in a CSV file in the working directory:

```
token_usage_seed_42.csv
```

---

## What Gets Added to the Spec

For each endpoint and response code, the system adds:

- **Parameter examples** — realistic values for path, query, header, and cookie parameters.
- **Request body examples** — realistic payloads for POST/PUT/PATCH operations.
- **Response body examples** — realistic response payloads per HTTP status code, including error responses (4xx, 5xx).

---

## Rate Limiting

The system respects OpenRouter API limits:

- **60 requests/minute** (configurable via `RATE_LIMIT_REQUESTS_PER_MINUTE`)
- **100,000 tokens/minute** (configurable via `RATE_LIMIT_TOKENS_PER_MINUTE`)
- Automatic retry with exponential backoff on failures.

---

## Logging

Logs are written to both the console (with color) and a daily rotating file under `logs/`:

```
logs/openapi_improver_2026-03-11.log
```

Set `LOG_LEVEL=DEBUG` in `.env` for verbose output including raw LLM responses.
