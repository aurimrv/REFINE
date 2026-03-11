import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """
    Central configuration class loaded from environment variables and .env file.
    """

    # LLM
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_API_BASE: str = os.getenv("OPENAI_API_BASE", "https://openrouter.ai/api/v1")
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

    @classmethod
    def validate(cls) -> None:
        """Raise ValueError if required configuration is missing."""
        if not cls.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is not set. Please configure it in your .env file."
            )
