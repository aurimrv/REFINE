"""
main.py — OpenAPI Spec Improver
================================
Entry point for the multi-agent system that analyzes an OpenAPI specification
and produces an enriched version with realistic examples for every endpoint
and response code.

Usage
-----
    python main.py --api-spec <API_SPEC> [--llm-model <LLM_MODEL>]

Arguments
---------
    --api-spec   Path to the OpenAPI specification file (relative or absolute).
                 Example: restcountries.json  or  /data/specs/my-api.json
    --llm-model  LLM model identifier (overrides the LLM_MODEL env variable).
                 Example: openai/gpt-4o-mini

Environment
-----------
    Configuration is loaded from a .env file in the working directory.
    See .env.example for all available options.
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env before importing any module that reads Config
load_dotenv()

from src.agents.orchestrator_agent import OrchestratorAgent  # noqa: E402
from src.agents.llm_enrichment_agent import LLMAuthenticationError  # noqa: E402
from src.utils.config import Config  # noqa: E402
from src.utils.logger import setup_logger  # noqa: E402

logger = setup_logger("main")


def parse_args() -> argparse.Namespace:
    """Parse and validate command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="openapi-improver",
        description=(
            "Analyzes an OpenAPI specification and generates an enriched version "
            "with realistic examples for each endpoint and response code."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--api-spec",
        required=True,
        metavar="API_SPEC",
        help=(
            "Path to the OpenAPI specification file (JSON). "
            "Accepts both relative and absolute paths."
        ),
    )
    parser.add_argument(
        "--llm-model",
        required=False,
        metavar="LLM_MODEL",
        default=None,
        help=(
            "LLM model identifier to use for enrichment. "
            "Overrides the LLM_MODEL environment variable. "
            "Example: openai/gpt-4o-mini"
        ),
    )
    return parser.parse_args()


def resolve_spec_path(api_spec_arg: str) -> Path:
    """
    Resolve the spec file path, accepting both relative and absolute paths.
    Raises FileNotFoundError if the file does not exist.
    """
    path = Path(api_spec_arg)
    if not path.is_absolute():
        # Try relative to current working directory first
        cwd_path = Path.cwd() / path
        if cwd_path.exists():
            return cwd_path.resolve()
        # Try relative to the script's directory
        script_dir_path = Path(__file__).parent / path
        if script_dir_path.exists():
            return script_dir_path.resolve()
        raise FileNotFoundError(
            f"API spec file not found: '{api_spec_arg}'. "
            "Tried relative to CWD and script directory."
        )
    if not path.exists():
        raise FileNotFoundError(f"API spec file not found at absolute path: '{path}'.")
    return path.resolve()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Resolve spec path
    try:
        spec_path = resolve_spec_path(args.api_spec)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    # Determine LLM model (CLI arg takes precedence over env var)
    llm_model = args.llm_model or Config.LLM_MODEL

    # Validate configuration
    try:
        Config.validate()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    logger.info("API spec resolved to: %s", spec_path)
    logger.info("LLM model: %s", llm_model)

    # Run the orchestrator
    try:
        orchestrator = OrchestratorAgent(spec_path=spec_path, llm_model=llm_model)
        output_path = orchestrator.run()
        logger.info("Done. Enriched specification saved to: %s", output_path)
    except LLMAuthenticationError as exc:
        # Authentication errors already have a detailed message logged by the agent.
        # Exit immediately with a non-zero code — no stack trace needed.
        logger.error(
            "Pipeline aborted: %s\n"
            "Action required: set a valid OPENROUTER_API_KEY in your .env file.",
            exc,
        )
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        logger.error("Pipeline failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
