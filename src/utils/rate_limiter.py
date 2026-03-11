import time
import threading
from src.utils.logger import setup_logger

logger = setup_logger("rate_limiter")


class RateLimiter:
    """
    Token-bucket rate limiter to respect API rate limits (requests per minute).
    Thread-safe implementation using a lock.
    """

    def __init__(self, requests_per_minute: int) -> None:
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute
        self._lock = threading.Lock()
        self._last_call_time: float = 0.0

    def wait(self) -> None:
        """Block until the next request is allowed according to the rate limit."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call_time
            wait_time = self.min_interval - elapsed
            if wait_time > 0:
                logger.debug(
                    "Rate limiter: waiting %.2f seconds before next request.", wait_time
                )
                time.sleep(wait_time)
            self._last_call_time = time.monotonic()
