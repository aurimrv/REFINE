"""
OpenAPI Spec Improver — Entry Point
------------------------------------
CLI tool that enriches an OpenAPI specification with realistic examples
using an LLM, and optionally analyzes source code to detect discrepancies
between the specification and the implementation.

Usage:
    python main.py --api-spec <API_SPEC> [--api-src <SRC_HOME>] [--llm-model <MODEL>]

Arguments:
    --api-spec   Path to the OpenAPI specification file (JSON or YAML).
                 Accepts both relative and absolute paths.
    --api-src    (Optional) Path to the API source code directory.
                 When provided, the tool analyzes the implementation,
                 generates a discrepancy report, and produces an enriched
                 spec that is 100% aligned with the implementation.
    --llm-model  (Optional) LLM model identifier to use (e.g., openai/gpt-4o-mini).
                 Overrides the LLM_MODEL value in .env.
"""

import argparse
import sys
from pathlib import Path

# Load .env before importing any module that reads Config
from dotenv import load_dotenv

load_dotenv()

from src.agents.orchestrator_agent import OrchestratorAgent  # noqa: E402
from src.agents.llm_enrichment_agent import LLMAuthenticationError  # noqa: E402
from src.utils.config import Config  # noqa: E402
from src.utils.logger import setup_logger  # noqa: E402

logger = setup_logger("main")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "OpenAPI Spec Improver: enriches an OpenAPI specification with "
            "realistic examples using an LLM, and optionally detects discrepancies "
            "between the spec and the source code implementation."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Spec-only enrichment
  python main.py --api-spec restcountries.json

  # Enrichment + source code analysis
  python main.py --api-spec restcountries.json --api-src ./restcountries/

  # Specify LLM model explicitly
  python main.py --api-spec restcountries.json --llm-model openai/gpt-4o

  # Using absolute paths
  python main.py --api-spec /path/to/api-spec.json --api-src /path/to/src/
        """,
    )
    parser.add_argument(
        "--api-spec",
        required=True,
        metavar="API_SPEC",
        help=(
            "Path to the OpenAPI specification file (JSON or YAML). "
            "Accepts both relative and absolute paths."
        ),
    )
    parser.add_argument(
        "--api-src",
        required=False,
        default=None,
        metavar="SRC_HOME",
        help=(
            "Optional path to the API source code directory. "
            "When provided, the tool analyzes the implementation and generates "
            "a discrepancy report alongside the enriched specification."
        ),
    )
    parser.add_argument(
        "--llm-model",
        required=False,
        default=None,
        metavar="LLM_MODEL",
        help=(
            "LLM model identifier to use (e.g., openai/gpt-4o-mini). "
            "Overrides the LLM_MODEL value defined in the .env file."
        ),
    )
    return parser.parse_args()


def resolve_path(raw: str, must_exist: bool = True) -> Path:
    """
    Resolve a path string (relative or absolute) to an absolute Path.
    Raises SystemExit if must_exist=True and the path does not exist.
    """
    p = Path(raw).expanduser().resolve()
    if must_exist and not p.exists():
        logger.error("Path does not exist: %s", p)
        sys.exit(1)
    return p


def main() -> None:
    args = parse_args()

    # Validate configuration (API key presence)
    try:
        Config.validate()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    # Resolve --api-spec path
    spec_path = resolve_path(args.api_spec, must_exist=True)
    if not spec_path.is_file():
        logger.error("--api-spec must point to a file, not a directory: %s", spec_path)
        sys.exit(1)

    # Resolve --api-src path (optional)
    src_home: Path | None = None
    if args.api_src:
        src_home = resolve_path(args.api_src, must_exist=True)
        if not src_home.is_dir():
            logger.error("--api-src must point to a directory: %s", src_home)
            sys.exit(1)

    llm_model: str | None = args.llm_model or Config.LLM_MODEL

    logger.info("API spec resolved to: %s", spec_path)
    logger.info("LLM model: %s", llm_model)
    if src_home:
        logger.info("Source code directory: %s", src_home)

    # Run the orchestrator
    try:
        orchestrator = OrchestratorAgent(
            spec_path=spec_path,
            llm_model=llm_model,
            src_home=src_home,
        )
        output_path, report_path = orchestrator.run()
        logger.info("Done. Enriched specification saved to: %s", output_path)
        if report_path:
            logger.info("Discrepancy report saved to: %s", report_path)
    except LLMAuthenticationError as exc:
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
