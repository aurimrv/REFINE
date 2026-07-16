# REFINE (REst From code and INferred Enhancement)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> This repository is the artifact of the paper **"REFINE: REst From code and
> INferred Enhancement"**, accepted at the Tools Track of the XL Brazilian
> Symposium on Software Engineering (SBES'26). *(link/DOI to be added)*

**REFINE** is an open-source, LLM-based multi-agent tool that automatically
**aligns an OpenAPI specification with the API source code** and **enriches it
with realistic, domain-grounded examples**. Given an OpenAPI document and,
optionally, the API source code, REFINE produces an enriched specification
(phantom status codes removed, missing endpoints and codes added, examples
populated) and, when source code is provided, a structured Markdown
**discrepancy report** describing every divergence between the document and the
implementation.

> **The described API does NOT need to be running or reachable.**
> All processing is performed through *static analysis* of the spec file and the
> source code, combined with LLM inference. REFINE never issues HTTP requests to
> the API servers declared in the specification.

---

## Features

- **Spec-only enrichment** — Reads an OpenAPI document and adds realistic,
  named `example` values to every parameter, request body, and response code
  via the LLM. Multiple examples are generated per response code:
  - **2xx** codes: at least two examples (`typical`, `edge_case`).
  - **4xx/5xx** codes: at least three examples (`invalid_type`,
    `boundary_violation`, `null_or_missing`) designed to actually trigger the
    error.
- **Source-code analysis** (`--api-src`) — Scans the implementation (any
  mainstream language/framework) and uses the LLM to extract every implemented
  endpoint, its HTTP verb, parameters, and the status codes each handler can
  return (including implicit codes such as a 500 from an uncaught exception).
- **Discrepancy report** — When `--api-src` is provided, REFINE compares the
  spec against the implementation and writes a detailed Markdown report grouping
  every finding into one of five categories:
  - `MATCH` — endpoint, codes, and parameters fully aligned.
  - `MISSING_IN_IMPL` — declared in the spec but not found in the source.
  - `MISSING_IN_SPEC` — implemented in the source but absent from the spec.
  - `RETCODE_MISMATCH` — present in both, but response codes differ.
  - `PARAM_MISMATCH` — present in both, but parameters differ.
- **Implementation-aligned correction** — In spec+source mode the source code
  is treated as the ground truth: endpoints found only in the implementation are
  inserted into the enriched spec, the catch-all `default` response is expanded
  into the concrete codes the implementation returns, and explicit codes are
  reconciled with what the source actually emits.
- **Domain-aware example generation** — Examples are inferred from the
  endpoint's context (operation name, parameter names, descriptions, API title),
  so a parameter named `alpha2Code` in a country-data API receives `"DE"` rather
  than `"string"`. Multi-example structures are stored under the
  `x-parameter-examples` operation extension.
- **OAS-version-aware structural repair** — The enriched spec is validated
  against the official JSON Schema for the detected version and passed through a
  catalog of ten auto-repair rules (see below) so it passes validation in
  standard tooling such as Swagger Editor.
- **Reproducibility & cost transparency** — All LLM calls use a configurable
  seed; per-run token usage is logged to a CSV file so the dollar cost can be
  computed directly from the provider's pricing.

---

## Architecture

REFINE is organized as a coordinator (`OrchestratorAgent`) driving six task
agents, plus external services (the OpenRouter LLM gateway and the bundled
OpenAPI JSON Schemas).

```
main.py (CLI)
   |
   +-- OrchestratorAgent ............ coordinates the whole pipeline
          |-- SpecParserAgent ....... loads/parses the spec, detects OAS
          |                           version and base path
          |-- SourceAnalyzerAgent ... extracts implemented endpoints from
          |                           source code via LLM   (spec+source only)
          |-- DiscrepancyReporterAgent  compares spec vs. impl, writes the
          |                           Markdown report        (spec+source only)
          |-- LLMEnrichmentAgent ..... generates multiple named examples per
          |                           endpoint / response code via LLM
          |-- SpecValidatorAgent ..... validates against the OAS JSON Schema and
          |                           applies 10 auto-repair rules
          +-- SpecWriterAgent ........ merges examples, inserts impl-only
                                      endpoints, writes the enriched spec
```

A rendered diagram is available at [`docs/refine-architecture.pdf`](docs/refine-architecture.pdf).
For a file-by-file walkthrough see [`project_structure.md`](project_structure.md).

### Pipeline

REFINE runs in one of two modes, selected automatically by the presence of
`--api-src`:

**Mode A — spec-only** (`--api-src` omitted)

1. Parse the OpenAPI specification.
2. Enrich each endpoint with realistic examples via the LLM.
3. Write the enriched spec to disk.
4. Validate and auto-repair the result.
5. Log token usage.

**Mode B — spec + source** (`--api-src` provided)

1. Parse the OpenAPI specification.
2. Analyze the source code to extract implemented endpoints and status codes.
3. Compare spec vs. implementation and write the Markdown discrepancy report.
4. Reconcile status codes (expand `default`, align explicit codes) and queue
   impl-only endpoints for inclusion.
5. Enrich every endpoint with implementation-aware context via the LLM.
6. Write the enriched, implementation-aligned spec to disk.
7. Validate and auto-repair the result.
8. Log token usage.

---

## Requirements

**Software environment**
- **Python 3.10+**
- Operating system: tested on **Linux (Ubuntu 22.04 / Linux Mint)**; expected to
  work on macOS and Windows with Python 3.10+.
- **Internet access is required at run time**, because REFINE calls LLMs through
  the OpenRouter API.
- An **OpenRouter API key** is required (a paid third-party service). Get one at
  [openrouter.ai/keys](https://openrouter.ai/keys).

**Hardware**
- No special hardware is required. REFINE performs static analysis and delegates
  all model inference to the remote LLM provider, so a standard machine (2+ CPU
  cores, 4+ GB RAM) is sufficient. No GPU is needed.

**Python dependencies** (installed via `requirements.txt`):
`openai`, `python-dotenv`, `pydantic`, `colorlog`, `tenacity`, `jsonschema`,
`json_repair`.

---

## Installation

1. Clone the repository and install the dependencies:

```bash
git clone https://github.com/aurimrv/REFINE.git
cd REFINE
pip install -r requirements.txt
```

2. Create your configuration file and set your OpenRouter API key:

```bash
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY=<your key>
```

### Testing the installation

A ready-to-run example is bundled under `example/restcountries/`. From the
repository root, run REFINE in full mode (spec + source code):

```bash
python main.py \
  --api-spec example/restcountries/specification/restcountries_original.json \
  --api-src  example/restcountries/ \
  --llm-model moonshotai/kimi-k2-0905
```

**Expected result.** When the run finishes, REFINE writes three files next to
the input specification, inside `example/restcountries/specification/`:

- `restcountries_original_<timestamp>.json` — the enriched specification;
- `restcountries_original_discrepancy_<timestamp>.md` — the discrepancy report;
- `token_usage_<timestamp>.csv` — the token-usage log.

For reference, an example of each of these output files (generated by the
authors) is already available in that same folder, so you can compare your
results against the expected output.

---

## Usage

```bash
# Spec-only enrichment (no source code required)
python main.py --api-spec restcountries.json

# Enrichment + source-code analysis + discrepancy report
python main.py --api-spec restcountries.json --api-src ./restcountries/

# Specify the LLM model explicitly (overrides LLM_MODEL from .env)
python main.py --api-spec restcountries.json --llm-model openai/gpt-4o

# Absolute paths are also accepted
python main.py --api-spec /path/to/api-spec.json --api-src /path/to/src/
```

### Command-line arguments

| Argument | Required | Description |
|---|---|---|
| `--api-spec` | yes | Path to the OpenAPI specification file (JSON). Relative or absolute. |
| `--api-src` | no | Path to the API source-code directory. Enables Mode B (discrepancy report + implementation-aligned enrichment). |
| `--llm-model` | no | LLM model identifier (e.g. `openai/gpt-4o-mini`). Overrides `LLM_MODEL` in `.env`. |

### Output files

All outputs are written to the **same directory as the original spec file**.

| Mode | File | Description |
|---|---|---|
| A & B | `<spec_name>_<timestamp>.json` | Enriched specification (always produced). |
| B only | `<spec_name>_discrepancy_<timestamp>.md` | Markdown discrepancy report. |
| A & B | `token_usage_<timestamp>.csv` | Per-run token usage log. |

A run log is also written to `logs/` in the working directory.

The token-usage CSV has the columns: `timestamp`, `spec_file`, `src_home`,
`model`, `seed`, `input_tokens`, `output_tokens`.

---

## Configuration (`.env`)

| Variable | Description | Default |
|---|---|---|
| `OPENROUTER_API_KEY` | OpenRouter API key (get one at [openrouter.ai/keys](https://openrouter.ai/keys)) | *(required)* |
| `OPENROUTER_API_BASE` | OpenRouter API base URL | `https://openrouter.ai/api/v1` |
| `LLM_MODEL` | LLM model identifier | `openai/gpt-4o-mini` |
| `LLM_TEMPERATURE` | Sampling temperature for enrichment (source analysis always uses 0) | `0.7` |
| `LLM_SEED` | Reproducibility seed | `42` |
| `LOG_LEVEL` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) | `INFO` |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | Max LLM requests per minute | `60` |
| `RATE_LIMIT_TOKENS_PER_MINUTE` | Token-per-minute budget (reserved) | `100000` |
| `RETRY_ATTEMPTS` | Retry attempts on transient errors | `3` |
| `RETRY_DELAY` | Initial retry delay (seconds) | `2.0` |
| `BACKOFF_FACTOR` | Exponential backoff multiplier | `3.0` |
| `OPENAPI_VERSION` | Default OAS version for schema selection and prompts (auto-detection overrides this per spec) | `3.0.0` |
| `SCHEMAS_DIR` | Directory holding the OpenAPI JSON Schemas | `./schemas` |

Authentication failures (HTTP 401/403) fail fast with a clear message instead of
exhausting the retry budget.

---

## OpenAPI version support

REFINE detects the version directly from the document (`swagger: "2.0"` vs.
`openapi: "3.x"`) and adapts prompts, structural repairs, and schema validation
accordingly. The bundled schemas live in `schemas/`:

- `openapi-2.0-schema.json` (Swagger 2.0)
- `openapi-3.0.0-schema.json` (OpenAPI 3.0.0)
- `openapi-3.1.0-schema.json` (OpenAPI 3.1.0)

### Auto-repair rules

| Rule | Applies to | Action |
|---|---|---|
| R1 | OAS 3.x | Convert `in: body` parameters to `requestBody`. |
| R2 | OAS 3.x | Convert `in: formData` parameters to `requestBody` (`application/x-www-form-urlencoded`). |
| R3 | OAS 3.x | Rename the `x-parameter-examples` extension to `x-examples` where needed. |
| R4 | OAS 3.x | Convert integer response-code keys to strings (`200` -> `"200"`). |
| R5 | all | Set `required: true` on every `in: path` parameter. |
| R6 | Swagger 2.0 | Move the invalid `example` field on parameters to `x-example`. |
| R7 | Swagger 2.0 | Remove the non-standard `originalRef` field (Springfox/Swagger-Core). |
| R8 | all | Insert a default `info.title` when missing. |
| R9 | all | Remove duplicate parameters (same `name` + `in`). |
| R10 | Swagger 2.0 | Add a default `consumes` for operations using `formData`. |

Errors that survive auto-repair are logged as warnings for manual review.

---

## Paper

This tool is described in the paper *"REFINE: REst From code and INferred
Enhancement"*, accepted at the Tools Track of the XL Brazilian Symposium on
Software Engineering (SBES'26). A link to the published version (or preprint)
will be added here.

**Paper:** *(link/DOI to be added)*

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## Project structure

A short overview (full walkthrough in [`project_structure.md`](project_structure.md)):

```
REFINE/
├── main.py                 # CLI entry point
├── requirements.txt        # Core dependencies
├── .env.example            # Configuration template
├── example/                # Ready-to-run example (restcountries) + sample outputs
├── docs/
│   ├── refine-architecture.pdf
│   └── project_structure.md
├── schemas/                # Bundled OpenAPI JSON Schemas (2.0, 3.0.0, 3.1.0)
└── src/
    ├── agents/             # Orchestrator + six task agents
    ├── models/             # Pydantic data models
    └── utils/              # Config, logging, rate limiting
```
