import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Root directory of the project (two levels up from this file: src/utils/ → project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Config:
    """
    Central configuration class loaded from environment variables and .env file.
    All LLM-provider settings use the OPENROUTER_* prefix to clearly identify
    OpenRouter as the LLM provider. The OpenAI-compatible client is used
    internally, but the credentials are OpenRouter-specific.
    """

    # OpenRouter credentials
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_API_BASE: str = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")

    # LLM model and sampling parameters
    LLM_MODEL: str = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    LLM_SEED: int = int(os.getenv("LLM_SEED", "42"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Rate limiting & retry
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "60"))
    RATE_LIMIT_TOKENS_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_TOKENS_PER_MINUTE", "100000"))
    RETRY_ATTEMPTS: int = int(os.getenv("RETRY_ATTEMPTS", "3"))
    RETRY_DELAY: float = float(os.getenv("RETRY_DELAY", "2.0"))
    BACKOFF_FACTOR: float = float(os.getenv("BACKOFF_FACTOR", "3.0"))

    # OpenAPI version for schema validation and LLM prompt guidance
    OPENAPI_VERSION: str = os.getenv("OPENAPI_VERSION", "3.0.0")

    # Directory where OpenAPI JSON Schemas are stored.
    # Schema files are expected to follow the naming convention:
    #   openapi-<OPENAPI_VERSION>-schema.json
    # e.g.: schemas/openapi-3.0.0-schema.json
    SCHEMAS_DIR: Path = Path(os.getenv("SCHEMAS_DIR", str(_PROJECT_ROOT / "schemas")))

    @classmethod
    def get_schema_path(cls) -> Path:
        """
        Return the path to the JSON Schema file for the configured OPENAPI_VERSION.
        Raises FileNotFoundError if the schema file does not exist.
        """
        schema_filename = f"openapi-{cls.OPENAPI_VERSION}-schema.json"
        schema_path = cls.SCHEMAS_DIR / schema_filename
        if not schema_path.exists():
            raise FileNotFoundError(
                f"OpenAPI schema file not found: {schema_path}\n"
                f"  → Download the schema for OpenAPI {cls.OPENAPI_VERSION} and place it at:\n"
                f"    {schema_path}"
            )
        return schema_path

    @classmethod
    def validate(cls) -> None:
        """Raise ValueError if required configuration is missing or invalid."""
        key = cls.OPENROUTER_API_KEY.strip()
        if not key:
            raise ValueError(
                "OPENROUTER_API_KEY is not set.\n"
                "  → Open your .env file and set OPENROUTER_API_KEY to your OpenRouter API key.\n"
                "  → Obtain your key at: https://openrouter.ai/keys"
            )
        # Detect placeholder values copied verbatim from .env.example
        if key.startswith("sk-or-v1-your") or key == "sk-or-v1-your-key-here":
            raise ValueError(
                "OPENROUTER_API_KEY appears to contain a placeholder value.\n"
                "  → Replace it with your actual OpenRouter API key in the .env file.\n"
                "  → Obtain your key at: https://openrouter.ai/keys"
            )
