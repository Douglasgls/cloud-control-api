from enum import Enum
import logging
import time
from typing import Callable, TypeVar, Any
from threading import Lock

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenError(Exception):
    """Raised when an operation is attempted while the circuit breaker is OPEN."""
    pass


class CircuitBreaker:
    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exceptions: tuple = (Exception,),
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_state_change = time.monotonic()
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_state_change >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._last_state_change = time.monotonic()
                    logger.info("CircuitBreaker [%s] transitioned from OPEN to HALF_OPEN", self.name)
            return self._state

    def execute(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        current_state = self.state

        if current_state == CircuitState.OPEN:
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is OPEN. Service unavailable."
            )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exceptions as exc:
            self._on_failure(exc)
            raise

    def _on_success(self) -> None:
        with self._lock:
            if self._state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
                logger.info("CircuitBreaker [%s] successfully recovered, resetting to CLOSED", self.name)
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_state_change = time.monotonic()

    def _on_failure(self, exc: Exception) -> None:
        with self._lock:
            self._failure_count += 1
            logger.warning(
                "CircuitBreaker [%s] failure #%d/%d: %s",
                self.name,
                self._failure_count,
                self.failure_threshold,
                exc,
            )

            if self._failure_count >= self.failure_threshold or self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._last_state_change = time.monotonic()
                logger.error("CircuitBreaker [%s] tripped! State is now OPEN.", self.name)
